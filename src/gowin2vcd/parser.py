"""
Gowin GAO CSV parser.

Built on top of the single-pass :class:`Scanner <gowin2vcd.scanner.Scanner>`.

Usage::

    parser = GowinCSVParser("capture.csv")
    capture = parser.parse()          # materialised Capture
    # or
    for sample in parser.iter_samples():  # lazy streaming
        ...
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .exceptions import EmptyCapture
from .exceptions import ParseError
from .model import Capture
from .model import Group
from .model import Metadata
from .model import Sample
from .model import Signal
from .scanner import Scanner


class GowinCSVParser:
    """Parse a Gowin GAO CSV file into structured data types.

    The parser opens the file **exactly once** via the :class:`Scanner`.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._scanner = Scanner(self._path)

        # Populated after first scan
        self._metadata: Metadata | None = None
        self._signals: list[Signal] | None = None
        self._groups: list[Group] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def metadata(self) -> Metadata:
        """Metadata extracted from the CSV header (lazy)."""
        if self._metadata is None:
            self._lazy_init()
        assert self._metadata is not None
        return self._metadata

    @property
    def signals(self) -> list[Signal]:
        """Signal definitions (lazy)."""
        if self._signals is None:
            self._lazy_init()
        assert self._signals is not None
        return self._signals

    @property
    def groups(self) -> list[Group]:
        """Group definitions from the ``Groups:`` section (lazy)."""
        if self._groups is None:
            self._lazy_init()
        assert self._groups is not None
        return self._groups

    def parse(self) -> Capture:
        """Parse the entire file and return a materialised :class:`Capture`.

        This reads all samples into memory. For large captures, prefer
        :meth:`iter_samples` for streaming.
        """
        samples = list(self.iter_samples())
        if not samples:
            raise EmptyCapture("Capture contains no samples.")

        # Populate metadata.groups with the parsed groups
        meta = self.metadata
        meta.groups = self.groups

        return Capture(
            metadata=meta,
            signals=self.signals,
            samples=samples,
        )

    def iter_samples(self) -> Iterator[Sample]:
        """Lazily iterate over samples without loading everything into memory.

        Yields :class:`Sample` objects one at a time.
        """
        result = self._scanner.scan()
        self._build_metadata(result)
        self._build_signals(result)
        self._build_groups(result)

        header = result.header
        if not header:
            raise ParseError("No signal header found in CSV data section.")

        for row in result.rows:
            if not row or not row[0].strip():
                continue
            try:
                timestamp = int(float(row[0]))
            except (ValueError, IndexError) as exc:
                raise ParseError(
                    f"Could not parse timestamp from row: {row!r}"
                ) from exc

            values: dict[str, str] = {}
            for name, value in zip(header[1:], row[1:]):
                values[name] = value

            yield Sample(timestamp=timestamp, values=values)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lazy_init(self) -> None:
        """Run a full scan to populate metadata, signals, and groups."""
        result = self._scanner.scan()
        self._build_metadata(result)
        self._build_signals(result)
        self._build_groups(result)
        # Consume rows to free the file handle (we don't need them here)
        if result.rows:
            for _ in result.rows:
                pass

    def _build_metadata(self, result) -> None:
        """Convert raw metadata dict into a :class:`Metadata` instance."""
        raw = result.metadata
        time_unit = raw.get("time_unit", "ns")

        # Also check the first column of the data header for time unit,
        # e.g. "time unit: us" or "time(us)"
        header = result.header
        if header and ":" in header[0]:
            parts = header[0].split(":", 1)
            if len(parts) == 2:
                candidate = parts[1].strip().lower()
                if candidate in ("us", "ns", "ms", "ps", "s"):
                    time_unit = candidate

        meta = Metadata(
            time_unit=time_unit,
            radix=raw.get("radix", "hex"),
            clock_name=raw.get("clock_name"),
            clock_period=raw.get("clock_period"),
        )
        # Store extra fields that don't have dedicated attributes
        extra = {k: v for k, v in raw.items() if k not in (
            "time_unit", "radix", "clock_name", "clock_period",
        )}
        if extra:
            meta.extra = extra
        self._metadata = meta

    def _build_signals(self, result) -> None:
        """Convert header column names into :class:`Signal` instances."""
        header = result.header
        if not header:
            raise ParseError("No signal header found in CSV data section.")

        # The first column is the timestamp column
        signal_names = header[1:]

        # Determine radix from metadata if available
        default_radix = result.metadata.get("radix", "hex")

        signals: list[Signal] = []
        for name in signal_names:
            # Check for alias pattern: "path/to/signal=alias"
            alias = None
            fullname = name
            m = re.match(r"^(.+)=([^=]+)$", name)
            if m:
                fullname = m.group(1).strip()
                alias = m.group(2).strip()

            sig = Signal(fullname=fullname, radix=default_radix, alias=alias)
            signals.append(sig)

        self._signals = signals

    def _build_groups(self, result) -> None:
        """Convert raw group dicts into :class:`Group` instances."""
        groups: list[Group] = []
        # Build a lookup table: original header name -> Signal
        # (original header names may include aliases like "path/to/sig=alias")
        signal_map: dict[str, Signal] = {}
        if self._signals is not None:
            header = result.header
            if header:
                # Map each original header column name to its Signal instance
                for hdr_name, sig in zip(header[1:], self._signals):
                    signal_map[hdr_name] = sig
                    # Also map by the stripped fullname
                    signal_map[sig.fullname] = sig
                    if sig.alias:
                        signal_map[sig.alias] = sig

        for raw in result.groups:
            group_signals: list[Signal] = []
            for sig_name in raw.get("signals", []):
                matched = signal_map.get(sig_name)
                if matched is not None:
                    group_signals.append(matched)
            groups.append(Group(
                name=raw.get("name", "unnamed"),
                signals=group_signals,
                radix=raw.get("radix", "hex"),
                mode=raw.get("mode", "asi"),
            ))
        self._groups = groups
