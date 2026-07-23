"""
Cross-validation tests.

Parse CSV → write VCD → read VCD back → compare samples.
Every reconstructed sample must match the original CSV.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gowin2vcd.parser import GowinCSVParser
from gowin2vcd.vcd import VCDWriter
from gowin2vcd.vcd_reader import VCDReader

# CSV fixtures for cross-validation
CROSS_VALIDATE_CSVS = [
    # (name, csv_content)
    ("basic", """\
Data:
time,clk,rst
0,0,1
1,1,0
2,0,1
"""),
    ("hex_bus", """\
Radix: hex
Data:
time,data[7:0]
0,00
1,AB
2,FF
"""),
    ("hierarchical", """\
Data:
time,top/clk,top/rst,top/uut/data[7:0]
0,0,1,00
1,1,0,AB
2,0,1,CD
"""),
    ("groups", """\
Groups:
my_bus, top/uut/data[7:0]
Data:
time,top/clk,top/rst,top/uut/data[7:0]
0,0,1,00
1,1,0,AB
"""),
    ("single_sample", """\
Data:
time,sig
0,1
"""),
    ("inline_data", """\
Data: time,clk,rst
0,0,1
1,1,0
"""),
]


def _csv_to_binary(raw: str, width: int) -> str:
    """Normalise a CSV value to the binary form VCD would produce.

    Handles the ambiguity of values like '00' which could be binary
    or hex depending on the signal width.
    """
    raw = raw.strip()
    if raw == "":
        return "x" * max(width, 1)

    # Single-bit signals: treat as binary
    if width == 1:
        if raw.lower() in ("0", "1", "x", "z"):
            return raw
        return "x"

    # Multi-bit: if it looks like binary with the right length, keep it
    if all(c in "01" for c in raw) and len(raw) == width:
        return raw

    # Multi-bit: if it looks like hex, convert to binary
    try:
        val = int(raw, 16)
        return format(val, f"0{width}b")
    except ValueError:
        pass

    # Fallback: try decimal
    try:
        val = int(raw)
        return format(val, f"0{width}b")
    except ValueError:
        return "x" * width


@pytest.mark.parametrize(
    "name,csv_content",
    CROSS_VALIDATE_CSVS,
    ids=lambda p: p[0] if isinstance(p, tuple) else str(p),
)
def test_cross_validate(name: str, csv_content: str, tmp_path) -> None:
    """Verify round-trip: CSV → VCD → VCD reader → matches original."""
    csv_path = tmp_path / f"{name}.csv"
    vcd_path = tmp_path / f"{name}.vcd"

    csv_path.write_text(csv_content)

    # Parse CSV
    parser = GowinCSVParser(str(csv_path))
    original_signals = parser.signals
    original_samples = list(parser.iter_samples())

    # Write VCD
    writer = VCDWriter(str(vcd_path), add_date=False, add_version=False)
    writer.write(parser)

    # Read VCD back
    reader = VCDReader(str(vcd_path))
    vcd_signals = reader.read_signals()
    vcd_samples = list(reader.iter_samples())

    # Compare signal count
    assert len(vcd_signals) == len(original_signals), (
        f"Signal count mismatch: VCD={len(vcd_signals)} CSV={len(original_signals)}"
    )

    # Compare sample count
    assert len(vcd_samples) == len(original_samples), (
        f"Sample count mismatch: VCD={len(vcd_samples)} CSV={len(original_samples)}"
    )

    # Compare each sample
    for i, (orig, vcd) in enumerate(zip(original_samples, vcd_samples)):
        assert orig.timestamp == vcd.timestamp, (
            f"Sample {i}: timestamp mismatch: VCD={vcd.timestamp} CSV={orig.timestamp}"
        )

        # Compare each signal value
        for sig in original_signals:
            orig_val = orig.values.get(sig.fullname, "")
            vcd_val = vcd.values.get(sig.fullname, "")

            # Convert CSV value to binary for comparison
            expected = _csv_to_binary(orig_val, sig.width)

            if vcd_val != expected:
                pytest.fail(
                    f"Sample {i}, signal '{sig.fullname}': "
                    f"VCD='{vcd_val}' expected='{expected}' (CSV='{orig_val}')"
                )