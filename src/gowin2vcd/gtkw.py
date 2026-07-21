"""
GTKWave save-file generator (``.gtkw``).

Produces a save file that GTKWave can load directly, with scopes
expanded and buses organised into groups from the ``Groups:`` section.
"""

from __future__ import annotations

from .model import Capture
from .model import Group


class GTKWSaveWriter:
    """Write a GTKWave save file (``.gtkw``).

    Parameters
    ----------
    filename:
        Output path for the ``.gtkw`` file.
    use_groups:
        If ``True`` (default), use the ``Groups:`` section from the capture
        to organise signals into GTKWave groups.  Signals not belonging
        to any group are listed individually under their scope.
    expand_scopes:
        If ``True`` (default), emit ``#scope/path`` markers so GTKWave
        expands the hierarchy on load.
    """

    def __init__(
        self,
        filename: str,
        *,
        use_groups: bool = True,
        expand_scopes: bool = True,
    ) -> None:
        self.filename = filename
        self._use_groups = use_groups
        self._expand_scopes = expand_scopes

    def write(self, capture: Capture) -> None:
        """Generate a .gtkw save file from a parsed capture."""
        with open(self.filename, "w") as fp:
            fp.write("[*] GTKWave Analyzer Save File\n")

            if self._use_groups and capture.metadata.groups:
                self._write_grouped(fp, capture)
            else:
                self._write_scoped(fp, capture)

    # ------------------------------------------------------------------
    # Internal — grouped layout (preferred)
    # ------------------------------------------------------------------

    def _write_grouped(self, fp, capture: Capture) -> None:
        """Write save file using Groups: section for signal organisation."""
        assigned: set[str] = set()

        for group in capture.metadata.groups:
            fp.write(f"\n#Group: {group.name}\n")
            for sig in group.signals:
                fp.write(f"{sig.fullname}\n")
                assigned.add(sig.fullname)

        # Remaining signals — group by scope
        remaining = [s for s in capture.signals if s.fullname not in assigned]
        if remaining:
            self._write_scoped_signals(fp, remaining)

    # ------------------------------------------------------------------
    # Internal — scope-based layout (fallback)
    # ------------------------------------------------------------------

    def _write_scoped(self, fp, capture: Capture) -> None:
        """Write save file with signals listed under their scopes."""
        self._write_scoped_signals(fp, capture.signals)

    def _write_scoped_signals(self, fp, signals) -> None:
        """Emit signals under ``#scope/path`` markers."""
        current_scope = None

        for signal in signals:
            scope = "/".join(signal.hierarchy)

            if scope != current_scope:
                fp.write(f"\n#{scope}\n")
                current_scope = scope

            fp.write(signal.fullname + "\n")