"""
FST (Fast Signal Trace) output backend.

Requires an external FST library such as ``pyfst`` or ``libfst``.
"""

from __future__ import annotations

from .writers import WaveWriter


class FSTWriter(WaveWriter):
    """Write waveform data in FST format."""

    def __init__(self, filename: str) -> None:
        self.filename = filename

    def write(self, parser) -> None:
        raise NotImplementedError(
            "FST support requires an external backend. "
            "See https://github.com/gtkwave/gtkwave for details."
        )