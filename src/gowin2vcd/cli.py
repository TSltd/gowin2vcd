"""
Command-line interface for gowin2vcd.
"""

from __future__ import annotations

import argparse
import sys

from .exceptions import EmptyCapture
from .exceptions import GowinError
from .exceptions import ParseError
from .exceptions import UnsupportedFormat
from .parser import GowinCSVParser
from .vcd import VCDWriter


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Convert Gowin GAO CSV captures to VCD waveform format.",
    )
    ap.add_argument("input", help="Path to the GAO CSV file")
    ap.add_argument("output", help="Output VCD file path (use .vcd.gz for gzip)")
    ap.add_argument(
        "--include",
        nargs="*",
        default=None,
        help="Only include these signals (full hierarchical names)",
    )
    ap.add_argument(
        "--exclude",
        nargs="*",
        default=None,
        help="Exclude these signals (full hierarchical names)",
    )
    ap.add_argument(
        "--no-date",
        action="store_false",
        dest="add_date",
        help="Omit the $date header from the VCD",
    )
    ap.add_argument(
        "--no-version",
        action="store_false",
        dest="add_version",
        help="Omit the $version header from the VCD",
    )
    ap.add_argument(
        "--timescale",
        default=None,
        help="Override the timescale unit (e.g. 'ns', 'us', 'ps')",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    # Build include/exclude sets
    include_set: set[str] | None = None
    exclude_set: set[str] | None = None
    if args.include:
        include_set = set(args.include)
    elif args.exclude:
        exclude_set = set(args.exclude)

    try:
        parser = GowinCSVParser(args.input)

        writer = VCDWriter(
            args.output,
            include_signals=include_set,
            exclude_signals=exclude_set,
            add_date=args.add_date,
            add_version=args.add_version,
            timescale_unit=args.timescale,
            progress=None if args.quiet else _progress_cb,
        )

        stats = writer.write(parser)

        if not args.quiet:
            _print_summary(stats)

        return 0

    except FileNotFoundError as exc:
        print(f"Error: file not found — {exc.filename}", file=sys.stderr)
        return 1
    except ParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 1
    except UnsupportedFormat as exc:
        print(f"Unsupported format: {exc}", file=sys.stderr)
        return 1
    except EmptyCapture as exc:
        print(f"Empty capture: {exc}", file=sys.stderr)
        return 1
    except GowinError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


def _progress_cb(current: int, total: int) -> None:
    if total:
        print(f"\r  Processed {current}/{total} samples", end="", file=sys.stderr)
    else:
        print(f"\r  Processed {current} samples...", end="", file=sys.stderr)
    if current == total:
        print(file=sys.stderr)


def _print_summary(stats) -> None:
    print(f"  Signals:   {stats.signals}")
    print(f"  Samples:   {stats.samples}")
    print(f"  Changes:   {stats.value_changes}")
    print(f"  Duration:  {stats.duration} timestamps")
    print(f"  Runtime:   {stats.runtime:.2f}s")
    ratio = stats.compression_ratio
    if ratio is not None:
        print(f"  Ratio:     {ratio:.2f} (estimated)")
    print(f"  Output:    {stats.output_path} ({_fmt_size(stats.bytes_written)})")


def _fmt_size(bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} TB"