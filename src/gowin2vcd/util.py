"""
General utility functions for gowin2vcd.
"""

from __future__ import annotations

import re
from typing import Iterator
from typing import Literal
from typing import Tuple

from .model import Signal

BUS_RE = re.compile(r"\[(\d+):(\d+)\]")

HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
BIN_RE = re.compile(r"^[01]+$")

# ---------------------------------------------------------------------------
# Bus / signal name utilities
# ---------------------------------------------------------------------------


def bus_width(name: str) -> int:
    """
    Extract width from::

        foo[7:0]
        state[2:0]

    Returns 1 for scalars.
    """
    m = BUS_RE.search(name)
    if not m:
        return 1
    msb = int(m.group(1))
    lsb = int(m.group(2))
    return abs(msb - lsb) + 1


def strip_bus(name: str) -> str:
    """``foo[7:0]`` → ``foo``"""
    return BUS_RE.sub("", name)


def split_hierarchy(name: str) -> list[str]:
    """Split a hierarchical name into parts."""
    return [p for p in name.split("/") if p]


def is_binary(text: str) -> bool:
    """Check if *text* is a valid binary string."""
    return BIN_RE.fullmatch(text) is not None


def is_hex(text: str) -> bool:
    """Check if *text* is a valid hex string."""
    return HEX_RE.fullmatch(text) is not None


# ---------------------------------------------------------------------------
# Scope walker (replaces HierarchyBuilder)
# ---------------------------------------------------------------------------

ScopeAction = Literal["open", "close", "signal"]
ScopeEvent = Tuple[int, ScopeAction, str | Signal]


def walk_scopes(
    signals: list[Signal],
    root_name: str = "logic",
) -> Iterator[ScopeEvent]:
    """Walk the signal hierarchy and yield scope open/close/signal events.

    This is a **memory-efficient** replacement for :class:`HierarchyBuilder`.
    Instead of building a tree in memory, it derives scope transitions directly
    from the ordered signal list.

    Yields ``(depth, action, payload)`` tuples where:

    * ``depth`` is the nesting level (0 = root).
    * ``action`` is ``"open"``, ``"close"``, or ``"signal"``.
    * ``payload`` is the scope name (for open/close) or the :class:`Signal`
      instance (for signal).

    Example output::

        (0, "open", "logic")
        (1, "open", "top")
        (1, "signal", Signal("top/clk"))
        (1, "signal", Signal("top/rst"))
        (2, "open", "uut")
        (2, "signal", Signal("top/uut/data[7:0]"))
        (2, "signal", Signal("top/uut/valid"))
        (2, "close", "uut")
        (1, "close", "top")
        (0, "close", "logic")

    Signals are emitted in their original order within each scope.
    Scopes are emitted in the order they are first encountered.
    """
    # Current path of open scope names (excluding root)
    current_path: list[str] = []

    yield (0, "open", root_name)

    for sig in signals:
        sig_path = list(sig.hierarchy)

        # Find the common prefix length
        common = 0
        while (
            common < len(current_path)
            and common < len(sig_path)
            and current_path[common] == sig_path[common]
        ):
            common += 1

        # Close scopes that are no longer in the path
        while len(current_path) > common:
            closed = current_path.pop()
            yield (len(current_path) + 1, "close", closed)

        # Open new scopes
        for depth in range(common, len(sig_path)):
            part = sig_path[depth]
            current_path.append(part)
            yield (depth + 1, "open", part)

        # Emit the signal itself
        yield (len(sig_path) + 1, "signal", sig)

    # Close all remaining scopes
    while current_path:
        closed = current_path.pop()
        yield (len(current_path) + 1, "close", closed)
    yield (0, "close", root_name)