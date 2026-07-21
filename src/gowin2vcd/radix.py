"""
Value conversion utilities.
"""

from __future__ import annotations

import re

HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")
BIN_RE = re.compile(r"^[01]+$")


def detect_radix(value: str) -> str:

    value = value.strip()

    if value == "":
        return "unknown"

    if BIN_RE.fullmatch(value):
        return "bin"

    if HEX_RE.fullmatch(value):
        return "hex"

    try:
        int(value)
        return "dec"
    except ValueError:
        return "unknown"


def to_binary(value: str, width: int) -> str:

    value = value.strip()

    if value == "":
        return "x" * width

    # Handle X/Z values — both single ("x", "z") and multi-char ("xx", "zz")
    lower = value.lower()
    if set(lower) <= {"x"}:
        return "x" * width
    if set(lower) <= {"z"}:
        return "z" * width

    radix = detect_radix(value)

    if radix == "bin":
        return value.zfill(width)

    if radix == "hex":
        return format(int(value, 16), f"0{width}b")

    if radix == "dec":
        return format(int(value), f"0{width}b")

    return "x" * width