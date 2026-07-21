# gowin2vcd Architecture

## Design Principle

> The parser should know everything about the CSV. The writers (VCD, FST, GTKW, JSON...) should know nothing about CSV.

## Module Overview

### Core Data Types (`model.py`)

The foundation of the entire library. Defines five dataclasses:

- `Metadata` — capture metadata (time unit, radix, clock info, groups)
- `Signal` — a single signal with fullname, width, hierarchy, basename, alias
- `Sample` — a timestamped row of signal values
- `Group` — a named group of signals from the `Groups:` section
- `Capture` — a fully parsed capture combining metadata, signals, and samples

This module has **no intra-package imports** to avoid circular dependencies.

### Exceptions (`exceptions.py`)

Typed exception hierarchy:

```
GowinError
├── ParseError
├── UnsupportedFormat
├── EmptyCapture
└── TimestampOrderError
```

### Scanner (`scanner.py`)

Single-pass streaming scanner. Opens the file **exactly once**:

```
CSV file
  │
  ▼
Scanner._scan_fp()
  │
  ├── state = "header"   → extracts metadata
  ├── state = "groups"   → collects group rows
  └── state = "body"     → returns ScanResult with row iterator
```

`ScanResult` contains `metadata` (dict), `groups` (list of dicts), `header` (list of column names), and `rows` (iterator).

### Parser (`parser.py`)

Wraps the `Scanner` and enriches raw data into typed model objects:

- `GowinCSVParser.signals` — lazy property, scans once
- `GowinCSVParser.metadata` — lazy property
- `GowinCSVParser.groups` — lazy property
- `GowinCSVParser.parse()` — materialise everything (calls `iter_samples()`)
- `GowinCSVParser.iter_samples()` — lazy iterator over `Sample` objects

### Utility (`util.py`)

- `bus_width()` — extract width from `foo[7:0]`
- `walk_scopes()` — hierarchy scope walker (replaces `HierarchyBuilder`)
- Various string checking helpers

### Radix Conversion (`radix.py`)

- `detect_radix()` — auto-detect binary/hex/decimal
- `to_binary()` — convert any value to binary string with X/Z handling

### VCD Writer (`vcd.py`)

Streaming VCD writer with:

- Deterministic identifiers (stable ordering)
- Gzip-compressed output (`.vcd.gz`)
- Signal filtering (include/exclude)
- Progress callback
- Timestamp validation
- X/Z value propagation

### GTKW Writer (`gtkw.py`)

Generates `.gtkw` save files using `Groups:` section for signal organisation.

### FST Writer (`fst.py`)

Stub — requires external backend.

### CLI (`cli.py`)

`argparse`-based command line with clean error handling and typed exit codes.

## Data Flow

```
CSV file
  │
  ▼
Scanner (single pass)
  │
  ├── ScanResult.metadata  ──►  Metadata
  ├── ScanResult.groups    ──►  list[Group]
  ├── ScanResult.header    ──►  list[str]
  └── ScanResult.rows      ──►  list[Sample]
                                  │
                                  ▼
                              VCDWriter / GTKWSaveWriter / FSTWriter
```

## Writing a New Output Format

1. Create a new module (e.g. `json.py`)
2. Implement a class with a `write(parser)` method
3. The writer accesses `parser.signals`, `parser.metadata`, and `parser.iter_samples()`
4. Wire it into `cli.py`
