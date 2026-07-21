"""
Tests for Signal dataclass and bus-width extraction.
"""

from __future__ import annotations

import pytest

from gowin2vcd.model import Signal


class TestSignal:
    """Tests for the Signal dataclass."""

    def test_signal_creation(self) -> None:
        sig = Signal("top/clk")
        assert sig.fullname == "top/clk"
        assert sig.width == 1
        assert sig.hierarchy == ("top",)
        assert sig.basename == "clk"
        assert sig.radix == "hex"

    def test_signal_radix_override(self) -> None:
        sig = Signal("top/data", radix="bin")
        assert sig.radix == "bin"

    def test_deep_hierarchy(self) -> None:
        sig = Signal("top/middle/bottom/signal")
        assert sig.hierarchy == ("top", "middle", "bottom")
        assert sig.basename == "signal"

    def test_root_signal(self) -> None:
        sig = Signal("clk")
        assert sig.hierarchy == ()
        assert sig.basename == "clk"

    def test_bus_width_8(self) -> None:
        sig = Signal("top/data[7:0]")
        assert sig.width == 8

    def test_bus_width_32(self) -> None:
        sig = Signal("top/addr[31:0]")
        assert sig.width == 32

    def test_bus_width_reversed(self) -> None:
        sig = Signal("top/data[0:7]")
        assert sig.width == 8

    def test_bus_width_1(self) -> None:
        sig = Signal("top/flag[0:0]")
        assert sig.width == 1

    def test_bus_within_hierarchy(self) -> None:
        sig = Signal("top/uut/data_bus[15:0]")
        assert sig.width == 16
        assert sig.hierarchy == ("top", "uut")
        assert sig.basename == "data_bus[15:0]"

    def test_brackets_in_basename(self) -> None:
        sig = Signal("top/state[3:0]")
        assert sig.basename == "state[3:0]"

    def test_multiple_brackets_only_first_used(self) -> None:
        sig = Signal("top/foo[7:0]/bar")
        assert sig.width == 8


class TestBusWidth:
    """Standalone bus-width extraction tests."""

    def test_scalar(self) -> None:
        from gowin2vcd.util import bus_width
        assert bus_width("clk") == 1

    def test_standard_bus(self) -> None:
        from gowin2vcd.util import bus_width
        assert bus_width("data[7:0]") == 8

    def test_reversed_bus(self) -> None:
        from gowin2vcd.util import bus_width
        assert bus_width("data[0:31]") == 32

    def test_hierarchical_bus(self) -> None:
        from gowin2vcd.util import bus_width
        assert bus_width("top/uut/addr[15:0]") == 16