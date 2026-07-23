"""
Hierarchy reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from .model import Signal


@dataclass(slots=True)
class Scope:

    name: str

    children: dict[str, "Scope"] = field(default_factory=dict)

    signals: list[Signal] = field(default_factory=list)


class HierarchyBuilder:

    def build(self, signals: list[Signal]) -> Scope:

        root = Scope("logic")

        for signal in signals:

            scope = root

            for part in signal.hierarchy:

                if part not in scope.children:

                    scope.children[part] = Scope(part)

                scope = scope.children[part]

            scope.signals.append(signal)

        return root