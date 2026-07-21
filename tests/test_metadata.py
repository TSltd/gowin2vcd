"""
Tests for metadata extraction from GAO CSV files.
"""

from __future__ import annotations

import pytest

from gowin2vcd.model import Metadata


class TestMetadata:
    """Tests for the Metadata dataclass."""

    def test_default_values(self) -> None:
        meta = Metadata()
        assert meta.time_unit == "ns"
        assert meta.radix == "hex"
        assert meta.clock_name is None
        assert meta.clock_period is None
        assert meta.groups == []
        assert meta.extra == {}

    def test_custom_values(self) -> None:
        meta = Metadata(
            clock_name="sys_clk",
            clock_period=10.0,
            time_unit="us",
            radix="bin",
        )
        assert meta.clock_name == "sys_clk"
        assert meta.clock_period == 10.0
        assert meta.time_unit == "us"
        assert meta.radix == "bin"

    def test_extra_fields(self) -> None:
        meta = Metadata()
        meta.extra["frequency"] = 100.0
        assert meta.extra["frequency"] == 100.0

    def test_groups_default_to_empty_list(self) -> None:
        meta = Metadata()
        assert meta.groups == []

    def test_groups_custom(self) -> None:
        from gowin2vcd.model import Group
        from gowin2vcd.model import Signal

        sig = Signal("top/clk")
        group = Group(name="clocks", signals=[sig])
        meta = Metadata(groups=[group])
        assert len(meta.groups) == 1
        assert meta.groups[0].name == "clocks"
        assert meta.groups[0].signals[0].fullname == "top/clk"