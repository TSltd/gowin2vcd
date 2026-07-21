# Gowin GAO CSV File Format

The Gowin Logic Analyzer (GAO) exports captures as CSV files with a specific
structure. This document describes the format and its known variants.

## General Structure

A GAO CSV file has three sections:

1. **Header** — metadata lines (free text, one per row)
2. **Groups** — optional signal grouping definitions
3. **Data** — column headers followed by timestamped sample rows

## Section 1: Header

The header consists of one or more lines before the `Groups:` or `Data:`
marker. Each line is a free-text metadata field. Known fields:

| Field        | Example                   | Description                     |
| ------------ | ------------------------- | ------------------------------- |
| Clock period | `Clock period: 10.000 ns` | Sampling clock period           |
| Frequency    | `Frequency: 100 MHz`      | Sampling frequency              |
| Radix        | `Radix: hex`              | Default radix for value display |
| Clock name   | `Clock: sys_clk`          | Name of the sampling clock      |
| Time unit    | `Time unit: us`           | Time unit for timestamps        |

## Section 2: Groups (optional)

Introduced by a line starting with `Groups:`. Each subsequent line defines
a group:

```
Groups:
my_group_name, signal1_path, signal2_path, ...
another_group, sig_a, sig_b, sig_c
```

The first column is the group name; remaining columns are signal full paths.

## Section 3: Data

Introduced by a line starting with `Data:`. The next non-empty line is the
column header. The first column is the timestamp; remaining columns are signal
names.

```
Data:
time unit: us,top/clk,top/rst,top/uut/data[7:0]
0,0,1,00
1,1,1,AB
```

### Variants

- **Time unit in header**: `time unit: us` may appear in the first column
  of the data header row, or as a separate header line.
- **Aliases**: Signal names may include an alias: `top/clk=sys_clk`.
- **No Groups section**: The file may skip straight from header to `Data:`.
- **No header metadata**: The file may start directly with `Data:`.
- **Bare `Data:`**: `Data:` on its own line, followed by a header row.
- **Inline `Data:`**: `Data: time unit: us,sig1,sig2` on one line.
