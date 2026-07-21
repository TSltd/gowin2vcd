"""
Golden reference tests.

Each CSV in ``tests/golden/`` has a corresponding ``.vcd`` file with the
expected output. Tests verify that the generated VCD matches exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gowin2vcd.parser import GowinCSVParser
from gowin2vcd.vcd import VCDWriter

GOLDEN_DIR = Path(__file__).parent / "golden"


def _golden_csvs():
    """Discover all golden CSV files."""
    return sorted(GOLDEN_DIR.glob("*.csv"))


@pytest.mark.parametrize(
    "csv_path",
    _golden_csvs(),
    ids=lambda p: p.stem,
)
def test_golden(csv_path: Path, tmp_path) -> None:
    """Verify generated VCD matches the golden reference."""
    vcd_path = csv_path.with_suffix(".vcd")
    if not vcd_path.exists():
        pytest.skip(f"No golden reference: {vcd_path}")

    out = tmp_path / "out.vcd"
    parser = GowinCSVParser(str(csv_path))
    writer = VCDWriter(
        str(out),
        add_date=False,
        add_version=False,
    )
    writer.write(parser)

    generated = out.read_text()
    expected = vcd_path.read_text()

    assert generated == expected, (
        f"Mismatch for {csv_path.name}\n"
        f"Expected ({len(expected)} bytes) != Generated ({len(generated)} bytes)"
    )