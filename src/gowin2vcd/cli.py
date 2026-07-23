"""
Command-line interface for gowin2vcd.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .exceptions import EmptyCapture
from .exceptions import GowinError
from .exceptions import ParseError
from .exceptions import UnsupportedFormat
from .parser import GowinCSVParser
from .vcd import VCDWriter

logger = logging.getLogger("gowin2vcd")


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
        "--verify",
        action="store_true",
        help="Print per-signal change counts (diagnostic mode)",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    # Configure logging
    _setup_logging(args.quiet, args.verbose)

    # Build include/exclude sets
    include_set: set[str] | None = None
    exclude_set: set[str] | None = None
    if args.include:
        include_set = set(args.include)
    elif args.exclude:
        exclude_set = set(args.exclude)

    try:
        logger.info("Parsing %s", args.input)
        parser = GowinCSVParser(args.input)
        logger.debug("Found %d signals, %d groups", len(parser.signals), len(parser.groups))

        writer = VCDWriter(
            args.output,
            include_signals=include_set,
            exclude_signals=exclude_set,
            add_date=args.add_date,
            add_version=args.add_version,
            timescale_unit=args.timescale,
            progress=None if args.quiet else _progress_cb,
        )

        logger.info("Writing VCD to %s", args.output)
        stats = writer.write(parser)

        if args.verify and stats.per_signal_changes:
            _print_verify(stats)

        if not args.quiet:
            _print_summary(stats)

        return 0

    except FileNotFoundError as exc:
        logger.error("file not found — %s", exc.filename)
        return 1
    except ParseError as exc:
        logger.error("Parse error: %s", exc)
        return 1
    except UnsupportedFormat as exc:
        logger.error("Unsupported format: %s", exc)
        return 1
    except EmptyCapture as exc:
        logger.error("Empty capture: %s", exc)
        return 1
    except GowinError as exc:
        logger.error("Error: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Unexpected error: %s", exc)
        return 1


def _setup_logging(quiet: bool, verbose: bool) -> None:
    """Configure the root logger for gowin2vcd."""
    level = logging.WARNING
    if verbose:
        level = logging.DEBUG
    elif not quiet:
        level = logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)


def _progress_cb(current: int, total: int) -> None:
    if total:
        print(f"\r  Processed {current}/{total} samples", end="", file=sys.stderr)
    else:
        print(f"\r  Processed {current} samples...", end="", file=sys.stderr)
    if current == total:
        print(file=sys.stderr)


def _print_verify(stats) -> None:
    """Print per-signal change counts in a formatted table."""
    print("\n  Per-signal change counts:")
    changes = stats.per_signal_changes or {}
    max_name_len = max((len(name) for name in changes), default=0)
    max_count_len = max((len(str(c)) for c in changes.values()), default=0)
    for name, count in sorted(changes.items(), key=lambda x: -x[1]):
        print(f"    {name:<{max_name_len}}  {count:>{max_count_len}} changes")


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