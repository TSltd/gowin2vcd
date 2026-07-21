"""
Tests for VCD generation.
"""

from __future__ import annotations

import gzip

import pytest

from gowin2vcd.model import Capture
from gowin2vcd.model import Metadata
from gowin2vcd.model import Sample
from gowin2vcd.model import Signal
from gowin2vcd.model import Group
from gowin2vcd.vcd import IdentifierGenerator
from gowin2vcd.vcd import VCDWriter
from gowin2vcd.writers import ConversionStats


# ---------------------------------------------------------------------------
# Fake parser for testing the VCD writer in isolation
# ---------------------------------------------------------------------------

class FakeParser:
    """Simulates the parser interface for VCDWriter."""

    def __init__(
        self,
        signals: list[Signal],
        samples: list[Sample],
        metadata: Metadata | None = None,
    ) -> None:
        self._signals = signals
        self._samples = samples
        self._metadata = metadata or Metadata(time_unit="ns")
        self._sample_index = 0

    @property
    def signals(self) -> list[Signal]:
        return self._signals

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    def iter_samples(self):
        for s in self._samples:
            yield s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIdentifierGenerator:
    """Tests for the VCD identifier generator."""

    def test_first_is_exclamation(self) -> None:
        gen = IdentifierGenerator()
        assert gen.next() == "!"

    def test_second_is_double_quote(self) -> None:
        gen = IdentifierGenerator()
        assert gen.next() == "!"
        assert gen.next() == '"'

    def test_unique_ids(self) -> None:
        gen = IdentifierGenerator()
        ids = {gen.next() for _ in range(200)}
        assert len(ids) == 200

    def test_reset(self) -> None:
        gen = IdentifierGenerator()
        gen.next()
        gen.next()
        gen.reset()
        assert gen.next() == "!"

    def test_deterministic(self) -> None:
        gen1 = IdentifierGenerator()
        gen2 = IdentifierGenerator()
        for _ in range(100):
            assert gen1.next() == gen2.next()


class TestVCDWriter:
    """Tests for the VCD writer."""

    def test_write_simple(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("top/clk"), Signal("top/data[7:0]")]
        samples = [
            Sample(0, {"top/clk": "0", "top/data[7:0]": "00"}),
            Sample(1, {"top/clk": "1", "top/data[7:0]": "AB"}),
            Sample(2, {"top/clk": "0", "top/data[7:0]": "CD"}),
        ]
        parser = FakeParser(signals, samples, Metadata(time_unit="us"))

        writer = VCDWriter(str(out))
        stats = writer.write(parser)

        assert isinstance(stats, ConversionStats)
        assert stats.signals == 2
        assert stats.samples == 3
        assert stats.value_changes > 0
        assert stats.output_path == str(out)
        assert stats.bytes_written > 0

        content = out.read_text()
        assert "$timescale 1 us $end" in content
        assert "$var wire 1 ! clk $end" in content
        assert "$var wire 8 \" data[7:0] $end" in content
        assert "#1" in content
        assert "#2" in content

    def test_write_gzip(self, tmp_path) -> None:
        out = tmp_path / "out.vcd.gz"
        signals = [Signal("clk")]
        samples = [Sample(0, {"clk": "0"}), Sample(1, {"clk": "1"})]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out))
        stats = writer.write(parser)

        assert stats.output_path.endswith(".vcd.gz")
        # Verify it's valid gzip
        with gzip.open(str(out), "rt") as f:
            content = f.read()
        assert "$timescale 1 ns $end" in content
        assert "$var wire 1 ! clk $end" in content

    def test_header_options(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("clk")]
        samples = [Sample(0, {"clk": "0"})]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(
            str(out), add_date=False, add_version=False, timescale_unit="ps"
        )
        writer.write(parser)

        content = out.read_text()
        assert "$date" not in content
        assert "$version" not in content
        assert "$timescale 1 ps $end" in content

    def test_include_filter(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("top/clk"), Signal("top/rst")]
        samples = [
            Sample(0, {"top/clk": "0", "top/rst": "1"}),
            Sample(1, {"top/clk": "1", "top/rst": "0"}),
        ]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out), include_signals={"top/clk"})
        stats = writer.write(parser)
        assert stats.signals == 1
        assert stats.samples == 2

        content = out.read_text()
        assert "$var wire 1 ! clk $end" in content
        assert "rst" not in content

    def test_exclude_filter(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("top/clk"), Signal("top/rst")]
        samples = [
            Sample(0, {"top/clk": "0", "top/rst": "1"}),
            Sample(1, {"top/clk": "1", "top/rst": "0"}),
        ]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out), exclude_signals={"top/rst"})
        stats = writer.write(parser)
        assert stats.signals == 1
        # Only 1 change (clk goes 0→1 between dumpvars sample and sample #1)
        assert stats.value_changes == 1

    def test_deterministic_output(self, tmp_path) -> None:
        """Output should be deterministic for the same inputs (excluding date)."""
        out1 = tmp_path / "a.vcd"
        out2 = tmp_path / "b.vcd"
        signals = [Signal("top/b_sig"), Signal("top/a_sig")]
        samples = [Sample(0, {"top/b_sig": "0", "top/a_sig": "0"})]
        parser = FakeParser(signals, samples)

        writer1 = VCDWriter(str(out1), add_date=False, add_version=False)
        writer2 = VCDWriter(str(out2), add_date=False, add_version=False)
        writer1.write(parser)
        writer2.write(parser)

        assert out1.read_text() == out2.read_text()

    def test_timestamp_validation(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("clk")]
        samples = [
            Sample(0, {"clk": "0"}),
            Sample(5, {"clk": "1"}),
            Sample(3, {"clk": "0"}),  # out of order
        ]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out))
        with pytest.raises(ValueError, match="out of order"):
            writer.write(parser)

    def test_xz_propagation(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("top/data[7:0]")]
        samples = [
            Sample(0, {"top/data[7:0]": "xx"}),
            Sample(1, {"top/data[7:0]": "zz"}),
        ]
        parser = FakeParser(signals, samples, Metadata(radix="hex"))

        writer = VCDWriter(str(out))
        writer.write(parser)

        content = out.read_text()
        assert "bxxxxxxxx" in content
        assert "bzzzzzzzz" in content

    def test_empty_parser(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("clk")]
        samples: list[Sample] = []
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out))
        with pytest.raises(ValueError, match="Empty capture"):
            writer.write(parser)

    def test_progress_callback(self, tmp_path) -> None:
        out = tmp_path / "out.vcd"
        signals = [Signal("clk")]
        samples = [Sample(i, {"clk": str(i & 1)}) for i in range(10)]
        parser = FakeParser(signals, samples)

        calls = []

        def progress(current, total):
            calls.append((current, total))

        writer = VCDWriter(str(out), progress=progress)
        writer.write(parser)

        assert len(calls) > 0
        assert calls[-1] == (10, 10)

    def test_scope_structure(self, tmp_path) -> None:
        """Verify that hierarchical signals generate proper scope nesting."""
        out = tmp_path / "out.vcd"
        signals = [
            Signal("top/clk"),
            Signal("top/rst"),
            Signal("top/uut/data[7:0]"),
            Signal("top/uut/valid"),
        ]
        samples = [Sample(0, {s.fullname: "0" for s in signals})]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out))
        writer.write(parser)

        content = out.read_text()
        # Expect three $scope nested: logic -> top -> uut
        assert content.count("$scope") == 3
        assert content.count("$upscope") == 3
        # Signals should be inside the correct scope
        assert "clk" in content
        assert "data[7:0]" in content

    def test_no_value_change_omitted(self, tmp_path) -> None:
        """A signal that doesn't change should not emit a change line."""
        out = tmp_path / "out.vcd"
        signals = [Signal("clk")]
        samples = [
            Sample(0, {"clk": "0"}),
            Sample(1, {"clk": "0"}),  # no change
            Sample(2, {"clk": "1"}),  # change
        ]
        parser = FakeParser(signals, samples)

        writer = VCDWriter(str(out))
        writer.write(parser)

        # Dumpvars: 0!
        # Then at #1: clk=0 (no change, omitted)
        # Then at #2: clk=1 (change, emitted)
        content = out.read_text()
        assert content.count("0!") == 1  # once in dumpvars, not again
        assert content.count("1!") == 1  # once at #2