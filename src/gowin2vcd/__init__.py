"""
gowin2vcd — Gowin GAO CSV to VCD waveform converter.

Professional converter for Gowin GAO CSV captures.

Features
--------
* Automatic GAO format detection (single-pass streaming scanner)
* Hierarchical signal reconstruction (scope walker, no tree in memory)
* VCD generation with deterministic identifiers
* GTKWave save-file generation
* Optional FST output (requires external backend)
* Gzip-compressed output (``.vcd.gz``)
* Signal filtering (include / exclude)
* Progress callback for large captures
"""

from .version import __version__
from .parser import GowinCSVParser
from .vcd import VCDWriter
from .json import JSONWriter
from .gtkw import GTKWSaveWriter
from .writers import ConversionStats

__all__ = [
    "__version__",
    "GowinCSVParser",
    "VCDWriter",
    "JSONWriter",
    "GTKWSaveWriter",
    "ConversionStats",
]