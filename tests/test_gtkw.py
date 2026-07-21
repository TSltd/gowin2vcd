"""
Tests for GTKWave save-file generation.
"""

from __future__ import annotations

import pytest

from gowin2vcd.model import Capture
from gowin2vcd.model import Group
from gowin2vcd.model import Metadata
from gowin2vcd.model import Sample
from gowin2vcd.model import Signal
from gowin2vcd.gtkw import GTKWSaveWriter


class TestGTKWSaveWriter:
    """Tests for the GTKWave save-file writer."""

    def make_capture(
        self,
        signals: list[Signal],
        groups: list[Group] | None = None,
    ) -> Capture:
        samples = [Sample(0, {s.fullname: "0" for s in signals})]
        meta = Metadata(groups=groups or [])
        return Capture(metadata=meta, signals=signals, samples=samples)

    def test_write_basic(self, tmp_path) -> None:
        out = tmp_path / "out.gtkw"
        signals = [Signal("top/clk"), Signal("top/rst")]
        capture = self.make_capture(signals)

        writer = GTKWSaveWriter(str(out))
        writer.write(capture)

        content = out.read_text()
        assert "[*] GTKWave Analyzer Save File" in content
        assert "top/clk" in content
        assert "top/rst" in content

    def test_write_with_scope(self, tmp_path) -> None:
        out = tmp_path / "out.gtkw"
        signals = [
            Signal("top/clk"),
            Signal("top/rst"),
            Signal("top/uut/data[7:0]"),
        ]
        capture = self.make_capture(signals)

        writer = GTKWSaveWriter(str(out))
        writer.write(capture)

        content = out.read_text()
        # Should have scope markers
        assert "#top" in content
        assert "#top/uut" in content
        # Signals under correct scopes
        assert "top/clk" in content
        assert "top/uut/data[7:0]" in content

    def test_write_with_groups(self, tmp_path) -> None:
        out = tmp_path / "out.gtkw"
        sig_clk = Signal("top/clk")
        sig_rst = Signal("top/rst")
        sig_data = Signal("top/uut/data[7:0]")
        signals = [sig_clk, sig_rst, sig_data]

        groups = [
            Group(name="control", signals=[sig_clk, sig_rst]),
            Group(name="data_bus", signals=[sig_data]),
        ]
        capture = self.make_capture(signals, groups)

        writer = GTKWSaveWriter(str(out))
        writer.write(capture)

        content = out.read_text()
        assert "#Group: control" in content
        assert "#Group: data_bus" in content
        assert "top/clk" in content
        assert "top/uut/data[7:0]" in content

    def test_groups_with_remaining_signals(self, tmp_path) -> None:
        """Un-grouped signals should appear under their scope."""
        out = tmp_path / "out.gtkw"
        sig_clk = Signal("top/clk")
        sig_extra = Signal("top/extra")
        signals = [sig_clk, sig_extra]

        groups = [Group(name="clocks", signals=[sig_clk])]
        capture = self.make_capture(signals, groups)

        writer = GTKWSaveWriter(str(out))
        writer.write(capture)

        content = out.read_text()
        assert "#Group: clocks" in content
        assert "top/clk" in content
        assert "#top" in content
        assert "top/extra" in content

    def test_no_groups_fallback(self, tmp_path) -> None:
        """Without groups, signals should be under scope markers."""
        out = tmp_path / "out.gtkw"
        signals = [Signal("top/clk")]
        capture = self.make_capture(signals)

        writer = GTKWSaveWriter(str(out), use_groups=False)
        writer.write(capture)

        content = out.read_text()
        assert "#top" in content

    def test_deterministic_output(self, tmp_path) -> None:
        """Same input should produce identical output."""
        out1 = tmp_path / "a.gtkw"
        out2 = tmp_path / "b.gtkw"
        signals = [Signal("top/a"), Signal("top/b")]
        capture = self.make_capture(signals)

        GTKWSaveWriter(str(out1)).write(capture)
        GTKWSaveWriter(str(out2)).write(capture)

        assert out1.read_text() == out2.read_text()