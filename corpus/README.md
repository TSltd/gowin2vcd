# GAO CSV Regression Corpus

This directory holds a collection of Gowin GAO CSV captures for regression testing.
Every parser improvement gets run against every capture.

## Structure

```
corpus/
├── README.md
├── hex/         — hex radix captures
├── binary/      — binary radix captures
├── decimal/     — decimal radix captures
├── aliases/     — captures with path/to/sig=alias_name syntax
├── groups/      — captures with Groups: section
├── simple/      — minimal captures (no metadata, no groups)
├── edge/        — edge cases (empty, single sample, etc.)
└── large/       — large captures for benchmarking
```

## Adding a capture

1. Place the CSV file in the appropriate subdirectory.
2. Optionally add a corresponding `.vcd` golden reference.
3. If adding to `large/`, include the sample count in the filename.
