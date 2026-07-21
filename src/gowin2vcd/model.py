"""
Core data types for gowin2vcd.

Every module imports from here. No duplicated classes.

This module intentionally has **no intra-package imports** to avoid
circular dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field
from typing import Iterator

# ---------------------------------------------------------------------------
# Bus-width extraction (inlined to avoid circular imports)
# ---------------------------------------------------------------------------

_BUS_RE = re.compile(r"\[(\d+):(\d+)\]")


def _bus_width(name: str) -> int:
    """Extract bus width from signal names like ``foo[7:0]``.

    Returns 1 for scalars.
    """
    m = _BUS_RE.search(name)
    if not m:
        return 1
    msb = int(m.group(1))
    lsb = int(m.group(2))
    return abs(msb - lsb) + 1


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Metadata:
    """Metadata extracted from a GAO CSV header."""

    clock_name: str | None = None
    clock_period: float | None = None
    time_unit: str = "ns"
    radix: str = "hex"
    groups: list[Group] | None = None
    extra: dict | None = None

    def __post_init__(self) -> None:
        if self.groups is None:
            self.groups = []
        if self.extra is None:
            self.extra = {}


@dataclass(slots=True)
class Signal:
    """A single signal from the capture.

    ``fullname`` is the original CSV column header, e.g. ``top/uut/clk[7:0]``.
    If the CSV includes an alias (e.g. ``top/clk=sys_clk``), ``alias`` will
    be set to the alias name and ``fullname`` will be the path before ``=``.

    ``width``, ``hierarchy``, and ``basename`` are derived automatically.
    """

    fullname: str
    radix: str = "hex"
    alias: str | None = None

    # Derived — computed in __post_init__
    width: int = field(init=False)
    hierarchy: tuple[str, ...] = field(init=False)
    basename: str = field(init=False)

    def __post_init__(self) -> None:
        self.width = _bus_width(self.fullname)
        parts = self.fullname.split("/")
        self.basename = parts[-1]
        self.hierarchy = tuple(parts[:-1])

    @property
    def display_name(self) -> str:
        """Return the alias if set, otherwise the basename."""
        return self.alias or self.basename


@dataclass(slots=True)
class Sample:
    """A single timestamped row of sample data."""

    timestamp: int
    values: dict[str, str]  # fullname -> raw value string


@dataclass(slots=True)
class Group:
    """A named group of signals from the ``Groups:`` section."""

    name: str
    signals: list[Signal]
    radix: str = "hex"
    mode: str = "asi"  # "asi" (analog signal interpolation) or "tdm"


@dataclass(slots=True)
class Capture:
    """Fully parsed capture — metadata, signals, and all samples."""

    metadata: Metadata
    signals: list[Signal]
    samples: list[Sample]

    @property
    def duration(self) -> int:
        """Total simulation time spanned by the samples."""
        if not self.samples:
            return 0
        return self.samples[-1].timestamp - self.samples[0].timestamp

    @property
    def num_samples(self) -> int:
        return len(self.samples)

    @property
    def num_signals(self) -> int:
        return len(self.signals)

    def iter_samples(self) -> Iterator[Sample]:
        """Lazy iteration over samples."""
        return iter(self.samples)