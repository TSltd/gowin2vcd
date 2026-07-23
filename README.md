# gowin2vcd

Convert Gowin GAO CSV captures to VCD waveform format.

[![Tests](https://github.com/TSltd/gowin2vcd/actions/workflows/tests.yml/badge.svg)](https://github.com/TSltd/gowin2vcd/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/gowin2vcd)](https://pypi.org/project/gowin2vcd/)
[![Python versions](https://img.shields.io/pypi/pyversions/gowin2vcd)](https://pypi.org/project/gowin2vcd/)

## Features

- **Single-pass streaming parser** — opens the file exactly once, no matter how large
- **Automatic GAO format detection** — handles all known CSV variants
- **Real GAO capture validated**
- **Hierarchical signal reconstruction** — scope walker, no tree in memory
- **Deterministic VCD output** — same input always produces identical output
- **Gzip-compressed output** — use `.vcd.gz` to save space automatically
- **Signal filtering** — `--include` and `--exclude` options
- **JSON output**
- **GTKWave save files** — generates `.gtkw` files with groups and expanded scopes
- **Signal aliases** — preserves aliases from `path/to/sig=alias_name` CSV columns
- **X/Z value propagation** — handles unknown and high-impedance states
- **Progress callback** — for large captures
- **Conversion statistics**
- **Zero runtime dependencies** — pure Python 3.10+
- **Golden regression tests**

## Supported outputs

- VCD
- JSON
- GTKWave save files

## Installation

```bash
pip install gowin2vcd
```

Or from source:

```bash
git clone https://github.com/TSltd/gowin2vcd.git
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

# Include only selected signals
gowin2vcd capture.csv output.vcd \
    --include top/clk top/rst

# Exclude selected signals
gowin2vcd capture.csv output.vcd \
    --exclude top/debug_state

# Override the VCD timescale
gowin2vcd capture.csv output.vcd \
    --timescale ns

# Omit the VCD date/version headers
gowin2vcd capture.csv output.vcd \
    --no-date --no-version

# Diagnostic mode
gowin2vcd capture.csv output.vcd \
    --verify

# Quiet mode
gowin2vcd capture.csv output.vcd \
    --quiet

# Verbose logging
gowin2vcd capture.csv output.vcd \
    --verbose
```

### Python library

```python
from gowin2vcd import GowinCSVParser
from gowin2vcd import VCDWriter

# Parse a capture
parser = GowinCSVParser("capture.csv")

# Access metadata
print(f"Time unit: {parser.metadata.time_unit}")
print(f"Signals: {[s.fullname for s in parser.signals]}")
print(f"Groups: {[g.name for g in parser.groups]}")

# Print stats
print(f"Signals: {stats.signals}")
print(f"Samples: {stats.samples}")
print(f"Changes: {stats.value_changes}")
print(f"Runtime: {stats.runtime:.2f}s")
print(f"Output:  {stats.output_path}")

# Convert to VCD
writer = VCDWriter("output.vcd")
stats = writer.write(parser)
print(f"Wrote {stats.num_samples} samples with {stats.num_changes} changes")

# Or iterate lazily
for sample in parser.iter_samples():
    print(f"t={sample.timestamp} clk={sample.values.get('top/clk')}")
```

### JSON

```python
from gowin2vcd import JSONWriter

writer = JSONWriter("capture.json")
writer.write(parser)
```

### GTKWave save files

```python
from gowin2vcd import GowinCSVParser
from gowin2vcd import GTKWSaveWriter

parser = GowinCSVParser("capture.csv")
capture = parser.parse()

writer = GTKWSaveWriter("output.gtkw")
writer.write(capture)
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for details.

```

CSV
 │
 ▼             ┌──────────► VCD
Scanner ─► Parser ─┬──────► JSON
                   ├──────► GTKWave
                   └──────► FST (planned)
```

## File Format

See [docs/file_format.md](docs/file_format.md) for the GAO CSV format specification.

## Status

The project is feature-complete for VCD conversion and has been validated against
real Gowin GAO captures.

Current outputs:

- VCD
- JSON
- GTKWave save files

Python 3.10+
Zero runtime dependencies

## Roadmap

Planned for v1.0:

- VCD reader
- Round-trip verification
- Fuzz testing
- Performance benchmarks

## License

MIT
