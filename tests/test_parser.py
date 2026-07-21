"""
Tests for the GAO CSV parser.
"""

from __future__ import annotations

import io

import pytest

from gowin2vcd.exceptions import EmptyCapture
from gowin2vcd.exceptions import ParseError
from gowin2vcd.model import Capture
from gowin2vcd.model import Sample
from gowin2vcd.model import Signal
from gowin2vcd.parser import GowinCSVParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CSV = """\
Clock period: 10.000 ns
Radix: hex
Groups:
my_bus, top/uut/data[7:0], top/uut/valid
Data:
time unit: us,top/clk,top/rst,top/uut/data[7:0],top/uut/valid
0,0,1,00,0
1,1,1,AB,1
2,0,1,CD,1
3,1,0,EF,0
"""

SIMPLE_CSV = """\
Data:
time, sig_a, sig_b
0,0,1
1,1,0
2,0,1
"""

EMPTY_DATA_CSV = """\
Data:
time, sig
"""

ALIAS_CSV = """\
Data:
time,top/clk=sys_clk,top/rst=reset_n
0,0,1
1,1,0
"""

INLINE_DATA_CSV = """\
Data: time,top/clk,top/rst
0,0,1
1,1,0
"""


@pytest.fixture
def sample_csv(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(SAMPLE_CSV)
    return str(path)


@pytest.fixture
def simple_csv(tmp_path):
    path = tmp_path / "simple.csv"
    path.write_text(SIMPLE_CSV)
    return str(path)


@pytest.fixture
def empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(EMPTY_DATA_CSV)
    return str(path)


@pytest.fixture
def alias_csv(tmp_path):
    path = tmp_path / "alias.csv"
    path.write_text(ALIAS_CSV)
    return str(path)


@pytest.fixture
def inline_csv(tmp_path):
    path = tmp_path / "inline.csv"
    path.write_text(INLINE_DATA_CSV)
    return str(path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParser:
    """Tests for GowinCSVParser."""

    def test_parse_signals(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        signals = parser.signals
        assert len(signals) == 4
        assert signals[0].fullname == "top/clk"
        assert signals[1].fullname == "top/rst"
        assert signals[2].fullname == "top/uut/data[7:0]"
        assert signals[3].fullname == "top/uut/valid"

    def test_signal_widths(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        signals = parser.signals
        assert signals[0].width == 1  # clk
        assert signals[1].width == 1  # rst
        assert signals[2].width == 8  # data[7:0]
        assert signals[3].width == 1  # valid

    def test_signal_hierarchy(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        signals = parser.signals
        assert signals[0].hierarchy == ("top",)
        assert signals[2].hierarchy == ("top", "uut")

    def test_signal_basename(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        assert parser.signals[2].basename == "data[7:0]"

    def test_parse_metadata(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        meta = parser.metadata
        assert meta.time_unit == "us"
        assert meta.radix == "hex"
        assert meta.clock_period == 10.0

    def test_groups(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        groups = parser.groups
        assert len(groups) == 1
        assert groups[0].name == "my_bus"
        assert len(groups[0].signals) == 2
        assert groups[0].signals[0].fullname == "top/uut/data[7:0]"

    def test_parse_samples(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        capture = parser.parse()
        assert isinstance(capture, Capture)
        assert capture.num_samples == 4
        assert capture.num_signals == 4

    def test_sample_values(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        samples = list(parser.iter_samples())
        assert len(samples) == 4

        # First sample
        assert samples[0].timestamp == 0
        assert samples[0].values["top/clk"] == "0"
        assert samples[0].values["top/uut/data[7:0]"] == "00"

        # Second sample
        assert samples[1].timestamp == 1
        assert samples[1].values["top/clk"] == "1"
        assert samples[1].values["top/uut/data[7:0]"] == "AB"

    def test_sample_timestamps(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        timestamps = [s.timestamp for s in parser.iter_samples()]
        assert timestamps == [0, 1, 2, 3]

    def test_capture_duration(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        capture = parser.parse()
        assert capture.duration == 3

    def test_empty_capture(self, empty_csv: str) -> None:
        parser = GowinCSVParser(empty_csv)
        with pytest.raises(EmptyCapture):
            parser.parse()

    def test_iter_empty_capture(self, empty_csv: str) -> None:
        parser = GowinCSVParser(empty_csv)
        samples = list(parser.iter_samples())
        assert len(samples) == 0

    def test_lazy_iteration(self, sample_csv: str) -> None:
        parser = GowinCSVParser(sample_csv)
        it = parser.iter_samples()
        samples = list(it)
        assert len(samples) == 4

    def test_simple_csv(self, simple_csv: str) -> None:
        """Test a minimal CSV with no header metadata."""
        parser = GowinCSVParser(simple_csv)
        capture = parser.parse()
        assert capture.num_signals == 2
        assert capture.num_samples == 3
        assert parser.metadata.time_unit == "ns"  # default

    def test_parse_with_no_groups(self, simple_csv: str) -> None:
        parser = GowinCSVParser(simple_csv)
        assert parser.groups == []

    def test_parse_invalid_file(self, tmp_path) -> None:
        invalid = tmp_path / "invalid.txt"
        invalid.write_text("not a csv file\n")
        parser = GowinCSVParser(str(invalid))
        with pytest.raises(ParseError):
            parser.parse()

    # ------------------------------------------------------------------
    # Milestone 2: Alias support
    # ------------------------------------------------------------------

    def test_alias_parsing(self, alias_csv: str) -> None:
        """Signal aliases should be extracted from 'path=alias' syntax."""
        parser = GowinCSVParser(alias_csv)
        signals = parser.signals
        assert len(signals) == 2
        assert signals[0].fullname == "top/clk"
        assert signals[0].alias == "sys_clk"
        assert signals[0].display_name == "sys_clk"
        assert signals[1].fullname == "top/rst"
        assert signals[1].alias == "reset_n"
        assert signals[1].display_name == "reset_n"

    def test_alias_samples(self, alias_csv: str) -> None:
        """Samples should still be keyed by original header name."""
        parser = GowinCSVParser(alias_csv)
        samples = list(parser.iter_samples())
        assert len(samples) == 2
        # Values are keyed by the original header column name
        assert samples[0].values["top/clk=sys_clk"] == "0"
        assert samples[1].values["top/clk=sys_clk"] == "1"

    # ------------------------------------------------------------------
    # Milestone 2: CSV variant support
    # ------------------------------------------------------------------

    def test_inline_data_header(self, inline_csv: str) -> None:
        """Data: header on the same line as column names."""
        parser = GowinCSVParser(inline_csv)
        capture = parser.parse()
        assert capture.num_signals == 2
        assert capture.num_samples == 2
        assert capture.signals[0].fullname == "top/clk"
        assert capture.signals[1].fullname == "top/rst"

    def test_multiple_groups(self, tmp_path) -> None:
        """Multiple groups in the Groups: section."""
        csv_content = """\
Groups:
group_a, sig1, sig2
group_b, sig3
Data:
time,sig1,sig2,sig3
0,0,1,0
"""
        path = tmp_path / "multi_group.csv"
        path.write_text(csv_content)
        parser = GowinCSVParser(str(path))
        groups = parser.groups
        assert len(groups) == 2
        assert groups[0].name == "group_a"
        assert len(groups[0].signals) == 2
        assert groups[1].name == "group_b"
        assert len(groups[1].signals) == 1