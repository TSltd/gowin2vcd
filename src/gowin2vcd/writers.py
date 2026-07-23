"""
Shared writer infrastructure.

Provides abstract base classes for all waveform output formats.

    WaveWriter
        │
        └── ValueChangeWriter  (shared VC event logic)
                │
                ├── VCD
                ├── FST
                └── future formats
"""

from __future__ import annotations

import time
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import Callable
from typing import Iterator

from .model import Sample
from .model import Signal


# ---------------------------------------------------------------------------
# Conversion statistics (returned by every writer)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ConversionStats:
    """Rich conversion metrics returned by all writers."""

    samples: int = 0
    signals: int = 0
    value_changes: int = 0
    duration: int = 0
    runtime: float = 0.0
    bytes_written: int = 0
    output_path: str = ""
    per_signal_changes: dict[str, int] | None = None

    @property
    def compression_ratio(self) -> float | None:
        """Estimate compression ratio (0 = perfect, 1 = uncompressed)."""
        # Rough estimate: each sample needs about 2*num_signals bytes
        if self.samples > 0 and self.signals > 0:
            estimated_uncompressed = self.samples * self.signals * 2
            if estimated_uncompressed > 0:
                return round(self.bytes_written / estimated_uncompressed, 2)
        return None


# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------


class WaveWriter(ABC):
    """Abstract base for all waveform output writers.

    Subclasses implement :meth:`write`, which accepts a parser and
    returns a :class:`ConversionStats` instance.
    """

    @abstractmethod
    def write(self, parser) -> ConversionStats:
        """Write the waveform data.

        Parameters
        ----------
        parser:
            A parser instance providing ``.signals``, ``.metadata``,
            and ``.iter_samples()``.

        Returns
        -------
        ConversionStats
        """
        ...


# ---------------------------------------------------------------------------
# Value-change writer (shared logic for VCD, FST, etc.)
# ---------------------------------------------------------------------------


class ValueChangeWriter(WaveWriter):
    """Intermediate writer that consumes value-change events.

    Subclasses implement :meth:`_write_header`, :meth:`_write_value`,
    and :meth:`_write_timestamp`. The base class handles:

    * Iterating over parser samples
    * Tracking value changes (only emitting changed values)
    * Timing the conversion
    * Returning a :class:`ConversionStats`
    """

    def __init__(self, filename: str, *, progress: Callable[[int, int], None] | None = None) -> None:
        self.filename = filename
        self._progress = progress

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, parser) -> ConversionStats:
        """Write the entire capture.

        Returns a :class:`ConversionStats` instance.
        """
        start = time.perf_counter()

        signals = list(parser.signals)
        if not signals:
            raise ValueError("No signals to write.")

        # Phase 1: assign identifiers
        self._assign_ids(signals)

        # Phase 2: write header
        self._write_header(parser, signals)

        # Phase 3: get first sample for dumpvars / initial state
        it = parser.iter_samples()
        try:
            first = next(it)
        except StopIteration:
            raise ValueError("Empty capture — no samples to write.")

        # Phase 4: write initial values
        self._write_initial_values(signals, first)

        # Phase 5: write changes
        changes = 0
        per_signal: dict[str, int] = {s.fullname: 0 for s in signals}
        last_ts = first.timestamp
        sample_count = 1
        prev_values: dict[str, str] = {
            s.fullname: first.values.get(s.fullname, "x" * s.width)
            for s in signals
        }

        for sample in it:
            sample_count += 1
            if sample.timestamp < last_ts:
                raise ValueError(
                    f"Timestamps out of order: {sample.timestamp} < {last_ts}"
                )
            last_ts = sample.timestamp

            self._write_timestamp(sample.timestamp)

            for sig in signals:
                raw = sample.values.get(sig.fullname, "")
                bits = self._convert_value(raw, sig.width)
                if bits == prev_values.get(sig.fullname):
                    continue
                prev_values[sig.fullname] = bits
                ident = self._ids[sig.fullname]
                self._write_value(ident, bits)
                changes += 1
                per_signal[sig.fullname] += 1

            if self._progress and sample_count % 1000 == 0:
                self._progress(sample_count, 0)

        self._close()

        if self._progress:
            self._progress(sample_count, sample_count)

        elapsed = time.perf_counter() - start
        duration = last_ts - first.timestamp

        stats = ConversionStats(
            samples=sample_count,
            signals=len(signals),
            value_changes=changes,
            duration=duration,
            runtime=round(elapsed, 3),
            per_signal_changes=per_signal,
        )
        self._update_stats(stats)

        return stats

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _assign_ids(self, signals: list[Signal]) -> None:
        """Assign deterministic identifiers to each signal."""
        ...

    @abstractmethod
    def _write_header(self, parser, signals: list[Signal]) -> None:
        """Write the file header."""
        ...

    @abstractmethod
    def _write_initial_values(
        self, signals: list[Signal], sample: Sample
    ) -> None:
        """Write the initial value dump."""
        ...

    @abstractmethod
    def _write_timestamp(self, timestamp: int) -> None:
        """Write a timestamp marker."""
        ...

    @abstractmethod
    def _write_value(self, ident: str, bits: str) -> None:
        """Write a value change."""
        ...

    @abstractmethod
    def _close(self) -> None:
        """Finalise the output (close file, flush buffers)."""
        ...

    @abstractmethod
    def _update_stats(self, stats: ConversionStats) -> None:
        """Add file-size or format-specific stats."""
        ...

    # ------------------------------------------------------------------
    # Default value conversion (overridable)
    # ------------------------------------------------------------------

    def _convert_value(self, raw: str, width: int) -> str:
        """Convert a raw value string to a binary bit string.

        Override for format-specific conversion.
        """
        from .radix import to_binary

        return to_binary(raw, width)