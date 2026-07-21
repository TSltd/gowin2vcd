# gowin2vcd

Convert Gowin GAO CSV captures to VCD waveform format.

[![Tests](https://github.com/yourusername/gowin2vcd/actions/workflows/tests.yml/badge.svg)](https://github.com/yourusername/gowin2vcd/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/gowin2vcd)](https://pypi.org/project/gowin2vcd/)
[![Python versions](https://img.shields.io/pypi/pyversions/gowin2vcd)](https://pypi.org/project/gowin2vcd/)

## Features

- **Single-pass streaming parser** — opens the file exactly once, no matter how large
- **Automatic GAO format detection** — handles all known CSV variants
- **Hierarchical signal reconstruction** — scope walker, no tree in memory
- **Deterministic VCD output** — same input always produces identical output
- **Gzip-compressed output** — use `.vcd.gz` to save space automatically
- **Signal filtering** — `--include` and `--exclude` options
- **GTKWave save files** — generates `.gtkw` files with groups and expanded scopes
- **Signal aliases** — preserves aliases from `path/to/sig=alias_name` CSV columns
- **X/Z value propagation** — handles unknown and high-impedance states
- **Progress callback** — for large captures
- **Zero runtime dependencies** — pure Python 3.10+

## Installation

```bash
pip install gowin2vcd
```

Or from source:

```bash
git clone https://github.com/yourusername/gowin2vcd.git
cd gowin2vcd
pip install .
```

## Usage

### Command line

```bash
# Basic conversion
gowin2vcd capture.csv output.vcd

# Compressed output
gowin2vcd capture.csv output.vcd.gz

# Filter signals
gowin2vcd capture.csv filtered.vcd --include top/clk top/rst

# Override timescale
gowin2vcd capture.csv output.vcd --timescale ns

# Suppress progress output
gowin2vcd capture.csv output.vcd --quiet

# Generate GTKWave save file
gowin2vcd capture.csv output.vcd
# Then load output.vcd in GTKWave, or generate a .gtkw file
```

### Python library

```python
from gowin2vcd.parser import GowinCSVParser
from gowin2vcd.vcd import VCDWriter

# Parse a capture
parser = GowinCSVParser("capture.csv")

# Access metadata
print(f"Time unit: {parser.metadata.time_unit}")
print(f"Signals: {[s.fullname for s in parser.signals]}")
print(f"Groups: {[g.name for g in parser.groups]}")

# Convert to VCD
writer = VCDWriter("output.vcd")
stats = writer.write(parser)
print(f"Wrote {stats.num_samples} samples with {stats.num_changes} changes")

# Or iterate lazily
for sample in parser.iter_samples():
    print(f"t={sample.timestamp} clk={sample.values.get('top/clk')}")
```

### GTKWave save files

```python
from gowin2vcd.parser import GowinCSVParser
from gowin2vcd.gtkw import GTKWSaveWriter

parser = GowinCSVParser("capture.csv")
capture = parser.parse()

writer = GTKWSaveWriter("output.gtkw")
writer.write(capture)
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for details.

```
CSV → Scanner (single pass) → Parser → VCDWriter / GTKWSaveWriter / FSTWriter
```

## File Format

See [docs/file_format.md](docs/file_format.md) for the GAO CSV format specification.

## License

MIT
