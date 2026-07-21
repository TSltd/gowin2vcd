"""
Single-pass streaming scanner for Gowin GAO CSV files.

Opens the file exactly once and produces:

    ScanResult
        ├── metadata   (Metadata from header / Groups: section)
        ├── groups     (parsed group definitions)
        ├── header     (list of signal column names)
        └── rows       (iterator over data rows)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Iterator
from typing import TextIO

from .exceptions import ParseError

# ---------------------------------------------------------------------------
# GAO CSV variant — regex patterns
# ---------------------------------------------------------------------------

# Regex to match the time unit embedded in the first column header,
# e.g. "time unit: us" or "time(us)" or "time unit:ns"
TIME_UNIT_RE = re.compile(
    r"(?:time\s*unit\s*[:=]?\s*|time\s*[\(]?)(\w+)",
    re.IGNORECASE,
)

# Regex to match "Groups:" section header
GROUPS_HEADER_RE = re.compile(r"^\s*Groups\s*:", re.IGNORECASE)

# Regex to match "Data:" section header (also allow "Data" without colon)
DATA_HEADER_RE = re.compile(r"^\s*Data\s*:?\s*", re.IGNORECASE)

# Regex to match "Acquisition:" or "Acq:" header variants
ACQ_HEADER_RE = re.compile(r"^\s*(?:Acquisition|Acq)\s*:?\s*", re.IGNORECASE)

# Regex to match "Timestamp:" or "Time:" header variants
TIMESTAMP_HEADER_RE = re.compile(r"^\s*(?:Timestamp|Time)\s*:?\s*", re.IGNORECASE)

# Regex for alias detection — "path/to/signal=alias_name"
ALIAS_RE = re.compile(r"^(.+)=([^=]+)$")


@dataclass(slots=True)
class ScanResult:
    """Result of a single-pass scan over a GAO CSV file."""

    metadata: dict = field(default_factory=dict)
    groups: list[dict] = field(default_factory=list)
    header: list[str] = field(default_factory=list)
    rows: Iterator[list[str]] | None = None


class Scanner:
    """Single-pass streaming scanner.

    Usage::

        scanner = Scanner(path)
        result = scanner.scan()

        # Access metadata before iterating rows
        print(result.metadata)

        for row in result.rows:
            ...
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> ScanResult:
        """Open the file once and return a fully populated ScanResult.

        The caller **must** consume ``result.rows`` before the result
        goes out of scope, because the underlying file handle is tied to
        the iterator.
        """
        fp = self._path.open("r", encoding="utf-8", errors="replace", newline="")
        return self._scan_fp(fp)

    def scan_stream(self, stream: TextIO) -> ScanResult:
        """Scan from an already-open text stream."""
        return self._scan_fp(stream)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan_fp(self, fp: TextIO) -> ScanResult:
        reader = csv.reader(fp)

        # State machine: we walk through the file in order.
        state: str = "header"  # header -> groups -> data -> body
        result = ScanResult()

        groups_buf: list[list[str]] = []
        header: list[str] | None = None
        header_is_set = False

        for row in reader:
            if not row or not row[0].strip():
                continue

            first = row[0].strip()

            # ----------------------------------------------------------
            # Detect state transitions
            # ----------------------------------------------------------

            if DATA_HEADER_RE.match(first):
                # We've reached the Data: section.
                state = "body"
                # The data header is *usually* the next non-empty row,
                # but some variants put it on the same line. We handle
                # that by reading the remainder of *this* row.
                # Strip the "Data:" prefix from the first column to get
                # the actual first column name (e.g. "time" or "time unit: us")
                first_col = DATA_HEADER_RE.sub("", first).strip()
                tail = [c.strip() for c in row[1:] if c.strip()]
                if tail or first_col:
                    # "Data: time unit: us,sig1,sig2,..." or "Data: time,sig1,sig2"
                    header = [first_col] + tail if first_col else tail
                    continue
                else:
                    # "Data:" followed by a separate header row
                    header = self._read_data_header(reader)
                    # Header row was already consumed — return result immediately
                    # with the reader as the row source
                    result.header = header
                    result.groups = self._parse_groups(groups_buf)
                    result.rows = self._iter_rows(reader, None, header)
                    return result

            if GROUPS_HEADER_RE.match(first):
                state = "groups"
                # Remainder of this row may contain group data, but
                # groups usually occupy multiple lines.
                continue

            # ----------------------------------------------------------
            # Header section (before Groups: / Data:)
            # ----------------------------------------------------------

            if state == "header":
                self._process_meta_line(first, result.metadata)
                continue

            # ----------------------------------------------------------
            # Groups section
            # ----------------------------------------------------------

            if state == "groups":
                groups_buf.append(row)
                continue

            # ----------------------------------------------------------
            # Body section — yield data rows
            # ----------------------------------------------------------

            if state == "body":
                if header is None:
                    raise ParseError("Reached data rows without a header")
                result.header = header
                # Parse collected group lines
                result.groups = self._parse_groups(groups_buf)
                # Determine the row iterator
                result.rows = self._iter_rows(reader, row, header)
                return result

        # If we fall through, we never found Data:
        raise ParseError(
            "Could not locate 'Data:' section in CSV file. "
            "The file may not be a valid GAO export."
        )

    def _read_data_header(self, reader: csv.reader) -> list[str]:
        """Read the header row that follows a bare ``Data:`` line."""
        for row in reader:
            if not row or not row[0].strip():
                continue
            return [c.strip() for c in row if c.strip()]
        raise ParseError("Expected header row after 'Data:' line but found none.")

    def _iter_rows(
        self,
        reader: csv.reader,
        first_row: list[str] | None,
        header: list[str],
    ) -> Iterator[list[str]]:
        """Yield data rows, padding/truncating to header length."""
        if first_row is not None:
            yield [c.strip() for c in first_row]
        for row in reader:
            if not row or not row[0].strip():
                continue
            # Pad shorter rows with empty strings
            while len(row) < len(header):
                row.append("")
            yield [c.strip() for c in row[: len(header)]]

    def _process_meta_line(self, line: str, meta: dict) -> None:
        """Try to extract metadata from a free-text header line."""
        # Try time unit
        m = TIME_UNIT_RE.search(line)
        if m:
            unit = m.group(1).lower()
            # Normalise common variants
            unit_map = {
                "us": "us",
                "ns": "ns",
                "ms": "ms",
                "ps": "ps",
                "s": "s",
                "second": "s",
                "seconds": "s",
                "millisecond": "ms",
                "milliseconds": "ms",
                "microsecond": "us",
                "microseconds": "us",
                "nanosecond": "ns",
                "nanoseconds": "ns",
            }
            meta["time_unit"] = unit_map.get(unit, unit)

        # Try clock period / frequency
        # e.g. "Clock period: 10.000 ns", "Frequency: 100 MHz"
        clk = re.search(r"clock\s*period\s*[:=]?\s*([\d.]+)", line, re.IGNORECASE)
        if clk:
            meta["clock_period"] = float(clk.group(1))

        freq = re.search(r"frequency\s*[:=]?\s*([\d.]+)", line, re.IGNORECASE)
        if freq:
            meta["clock_frequency"] = float(freq.group(1))

        # Try radix
        rad = re.search(r"(?:radix|base)\s*[:=]?\s*(\w+)", line, re.IGNORECASE)
        if rad:
            meta["radix"] = rad.group(1).lower()

        # Try clock name
        clk_name = re.search(r"clock\s*[:=]?\s*(\S+)", line, re.IGNORECASE)
        if clk_name and "clock_period" not in meta and "clock_frequency" not in meta:
            meta["clock_name"] = clk_name.group(1)

    def _parse_groups(self, rows: list[list[str]]) -> list[dict]:
        """Parse group definitions from the ``Groups:`` section.

        The GAO format defines groups like::

            Groups:
            my_group_name, sig1_path, sig2_path, ...
            another_group, sig_a, sig_b, sig_c

        Some variants use trailing ``=`` in the group name::

            bus_name[7:0] =, bus_name[7], bus_name[6], ...

        Each row is a CSV record where the first column is the group name
        and the remaining columns are signal names.
        """
        groups: list[dict] = []
        for row in rows:
            if not row or not row[0].strip():
                continue
            name = row[0].strip()
            # Strip trailing "=" or "=," from group names
            name = name.rstrip("=,").strip()
            signals = [c.strip() for c in row[1:] if c.strip()]
            groups.append({"name": name, "signals": signals})
        return groups
