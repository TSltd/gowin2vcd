"""
IEEE-1364 VCD writer for gowin2vcd.

Features
--------
* Streaming writer — does not buffer all samples in memory.
* Deterministic identifier allocation (sorted by scope + signal name).
* Deterministic hierarchy ordering (scope walker instead of tree).
* Timestamp monotonicity validation.
* X/Z value propagation.
* Binary/hex/decimal conversion via ``radix.py``.
* Optional gzip-compressed output (auto-detected from ``.vcd.gz`` suffix).
* Optional progress callback for large conversions.
* Optional signal filtering (include / exclude lists).
"""

from __future__ import annotations

import datetime
import gzip
import os
from pathlib import Path
from typing import Callable
from typing import TextIO

from .model import Sample
from .model import Signal
from .util import walk_scopes
from .writers import ConversionStats
from .writers import ValueChangeWriter

# ---------------------------------------------------------------------------
# Progress callback signature
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int], None]  # current, total


# ---------------------------------------------------------------------------
# Deterministic identifier generator
# ---------------------------------------------------------------------------


class IdentifierGenerator:
    """Generates deterministic VCD identifiers.

    Identifiers are single printable ASCII characters first (``!`` .. ``~``),
    then two-character, three-character, etc. The order is deterministic
    based on the order ``.next()`` is called.
    """

    def __init__(self) -> None:
        self._i = 0

    def next(self) -> str:
        n = self._i
        self._i += 1
        s = ""
        while True:
            s = chr(33 + (n % 94)) + s
            n //= 94
            if n == 0:
                break
        return s

    def reset(self) -> None:
        """Reset the generator to the beginning."""
        self._i = 0


# ---------------------------------------------------------------------------
# Main VCD writer
# ---------------------------------------------------------------------------


class VCDWriter(ValueChangeWriter):
    """Streaming VCD writer.

    Parameters
    ----------
    filename:
        Output path. If it ends with ``.gz``, the output will be
        transparently gzip-compressed.
    include_signals:
        Optional set of signal fullnames to **include**.
        If *None*, all signals are included.
    exclude_signals:
        Optional set of signal fullnames to **exclude**.
        Ignored if *include_signals* is set.
    progress:
        Optional callback invoked as ``progress(current, total)``
        during sample processing.
    add_date:
        Include a ``$date`` header (default ``True``).
    add_version:
        Include a ``$version`` header (default ``True``).
    timescale_unit:
        Override the timescale unit (default uses metadata).
    """

    def __init__(
        self,
        filename: str | Path,
        *,
        include_signals: set[str] | None = None,
        exclude_signals: set[str] | None = None,
        progress: ProgressCallback | None = None,
        add_date: bool = True,
        add_version: bool = True,
        timescale_unit: str | None = None,
    ) -> None:
        super().__init__(str(filename))
        self._filename = Path(filename)
        self._include = include_signals
        self._exclude = exclude_signals
        self._progress = progress
        self._add_date = add_date
        self._add_version = add_version
        self._timescale_unit = timescale_unit

        # State set during write()
        self._fp: TextIO | None = None
        self._ids: dict[str, str] = {}
        self._previous: dict[str, str] = {}
        self._gen = IdentifierGenerator()
        self._parsed_signals: list[Signal] | None = None

    # ------------------------------------------------------------------
    # Override write() to apply filtering before delegating to parent
    # ------------------------------------------------------------------

    def write(self, parser) -> ConversionStats:
        # Apply include/exclude filters
        self._parsed_signals = list(parser.signals)
        signals = self._filter_signals(self._parsed_signals)
        if not signals:
            raise ValueError("No signals to write (all were filtered out).")

        # Wrap parser to return filtered signals
        class FilteredParser:
            @property
            def signals(self):
                return signals
            @property
            def metadata(self):
                return parser.metadata
            def iter_samples(self):
                return parser.iter_samples()

        return super().write(FilteredParser())

    def _filter_signals(self, signals: list[Signal]) -> list[Signal]:
        if self._include is not None:
            return [s for s in signals if s.fullname in self._include]
        if self._exclude is not None:
            return [s for s in signals if s.fullname not in self._exclude]
        return list(signals)

    # ------------------------------------------------------------------
    # ValueChangeWriter implementation
    # ------------------------------------------------------------------

    def _assign_ids(self, signals: list[Signal]) -> None:
        """Assign deterministic identifiers by walking scopes."""
        self._gen.reset()
        self._ids.clear()

        for _depth, action, payload in walk_scopes(signals):
            if action == "signal" and isinstance(payload, Signal):
                ident = self._gen.next()
                self._ids[payload.fullname] = ident

    def _write_header(self, parser, signals: list[Signal]) -> None:
        fp = self._open_output()
        self._fp = fp

        if self._add_date:
            fp.write(f"$date\n    {datetime.datetime.now()}\n$end\n")

        if self._add_version:
            fp.write("$version\n    gowin2vcd\n$end\n")

        unit = self._timescale_unit or parser.metadata.time_unit
        fp.write(f"$timescale 1 {unit} $end\n")

        for _depth, action, payload in walk_scopes(signals):
            if action == "open" and isinstance(payload, str):
                fp.write(f"$scope module {payload} $end\n")
            elif action == "close" and isinstance(payload, str):
                fp.write("$upscope $end\n")
            elif action == "signal" and isinstance(payload, Signal):
                ident = self._ids[payload.fullname]
                fp.write(
                    f"$var wire {payload.width} {ident} "
                    f"{payload.basename} $end\n"
                )

        fp.write("$enddefinitions $end\n")

    def _write_initial_values(
        self, signals: list[Signal], sample: Sample
    ) -> None:
        assert self._fp is not None
        fp = self._fp
        fp.write("$dumpvars\n")
        for sig in signals:
            ident = self._ids[sig.fullname]
            raw = sample.values.get(sig.fullname, "")
            bits = self._convert_value(raw, sig.width)
            self._previous[sig.fullname] = bits
            self._emit(fp, ident, bits)
        fp.write("$end\n")

    def _write_timestamp(self, timestamp: int) -> None:
        assert self._fp is not None
        self._fp.write(f"#{timestamp}\n")

    def _write_value(self, ident: str, bits: str) -> None:
        assert self._fp is not None
        self._emit(self._fp, ident, bits)

    def _close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def _update_stats(self, stats: ConversionStats) -> None:
        stats.output_path = str(self._filename)
        try:
            stats.bytes_written = os.path.getsize(self._filename)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_output(self) -> TextIO:
        path = self._filename
        if path.suffix == ".gz" or str(path).endswith(".gz"):
            return gzip.open(path, "wt", encoding="utf-8")
        return path.open("w", encoding="utf-8")

    @staticmethod
    def _emit(fp: TextIO, ident: str, bits: str) -> None:
        if len(bits) == 1:
            fp.write(f"{bits}{ident}\n")
        else:
            fp.write(f"b{bits} {ident}\n")