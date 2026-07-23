"""
VCD (Value Change Dump) reader.

Reads the subset of IEEE-1364 VCD that gowin2vcd emits and produces
a stream of :class:`Sample` objects, enabling round-trip verification.

Supported VCD subset:
* ``$scope`` / ``$upscope`` — hierarchy
* ``$var wire <width> <id> <name> $end`` — signal declarations
* ``$dumpvars`` — initial values
* ``#<timestamp>`` — time markers
* ``<bit><id>`` — scalar value changes
* ``b<binary> <id>`` — vector value changes
* ``x`` / ``z`` — unknown / high-impedance
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .model import Sample
from .model import Signal


# Regex patterns for VCD line types
_VAR_RE = re.compile(
    r"\$var\s+wire\s+(\d+)\s+(\S+)\s+(\S+)\s+\$end"
)
_TIMESTAMP_RE = re.compile(r"^#(\d+)$")
_SCALAR_RE = re.compile(r"^([01xzXZ])(\S+)$")
_VECTOR_RE = re.compile(r"^b([01xzXZ]+)\s+(\S+)$")


class VCDReader:
    """Read a VCD file and produce a stream of :class:`Sample` objects.

    Usage::

        reader = VCDReader("output.vcd")
        for sample in reader.iter_samples():
            print(sample.timestamp, sample.values)
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def read_signals(self) -> list[Signal]:
        """Parse the VCD header and return the list of signals."""
        return self._parse_header()[1]

    def iter_samples(self) -> Iterator[Sample]:
        """Iterate over samples in the VCD file.

        Yields :class:`Sample` objects with timestamp and values.
        """
        # Phase 1: parse header to build id→fullname mapping
        id_to_name, _ = self._parse_header()

        # Phase 2: read value changes
        # The VCD emits *only changes*, so we maintain a running state.
        # At each timestamp, we emit a complete snapshot of all signals.
        state: dict[str, str] = {}
        timestamp: int | None = None
        in_dumpvars = False
        dumpvars_done = False

        with self._path.open("r", encoding="utf-8") as fp:
            for line in fp:
                raw = line.strip()
                if not raw:
                    continue

                # Skip header directives until we hit $dumpvars
                if raw.startswith("$"):
                    if raw.startswith("$dumpvars"):
                        in_dumpvars = True
                    elif raw == "$end" and in_dumpvars:
                        in_dumpvars = False
                        dumpvars_done = True
                        # Yield initial state (complete snapshot)
                        if state:
                            yield Sample(timestamp=0, values=dict(state))
                    continue

                if in_dumpvars:
                    # Inside $dumpvars ... $end — these are initial values
                    self._parse_value_line(raw, id_to_name, state)
                    continue

                if not dumpvars_done:
                    continue

                # Data section
                ts_match = _TIMESTAMP_RE.match(raw)
                if ts_match:
                    # If we have a previous timestamp, emit the accumulated state
                    if timestamp is not None:
                        yield Sample(timestamp=timestamp, values=dict(state))
                    timestamp = int(ts_match.group(1))
                else:
                    # Value change line — updates state in-place
                    self._parse_value_line(raw, id_to_name, state)

            # Emit final sample
            if timestamp is not None and dumpvars_done:
                yield Sample(timestamp=timestamp, values=dict(state))

    def _parse_header(self) -> tuple[dict[str, str], list[Signal]]:
        """Parse the VCD header region (before $dumpvars).

        Returns (id_to_name, signals).
        """
        id_to_name: dict[str, str] = {}
        signals: list[Signal] = []
        scope_path: list[str] = []

        with self._path.open("r", encoding="utf-8") as fp:
            for line in fp:
                raw = line.strip()
                if not raw:
                    continue

                if raw.startswith("$scope"):
                    parts = raw.split()
                    if len(parts) >= 3:
                        scope_path.append(parts[2])

                elif raw.startswith("$upscope"):
                    if scope_path:
                        scope_path.pop()

                elif raw.startswith("$var"):
                    m = _VAR_RE.match(raw)
                    if m:
                        width = int(m.group(1))
                        ident = m.group(2)
                        name = m.group(3)
                        fullname = "/".join(scope_path + [name]) if scope_path else name
                        # Strip the artificial root scope "logic" if present
                        display_name = fullname
                        if display_name.startswith("logic/"):
                            display_name = display_name[len("logic/"):]
                        sig = Signal(fullname=display_name)
                        signals.append(sig)
                        id_to_name[ident] = display_name

                elif raw.startswith("$enddefinitions"):
                    break

        return id_to_name, signals

    @staticmethod
    def _parse_value_line(
        line: str,
        id_to_name: dict[str, str],
        values: dict[str, str],
    ) -> None:
        """Parse a single value-change line and update *values* in-place."""
        # Try vector first: b<binary> <id>
        vm = _VECTOR_RE.match(line)
        if vm:
            bits = vm.group(1)
            ident = vm.group(2)
            name = id_to_name.get(ident)
            if name:
                values[name] = bits
            return

        # Try scalar: <bit><id>
        sm = _SCALAR_RE.match(line)
        if sm:
            bit = sm.group(1)
            ident = sm.group(2)
            name = id_to_name.get(ident)
            if name:
                values[name] = bit
            return