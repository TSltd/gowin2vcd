"""
Tests for JSON waveform export.
"""

from __future__ import annotations

import json

import pytest

from gowin2vcd.model import Metadata
from gowin2vcd.model import Sample
from gowin2vcd.model import Signal
from gowin2vcd.json import JSONWriter


class FakeParser:
    def __init__(self, signals, samples, metadata=None):
        self._signals = signals
        self._samples = samples
        self._metadata = metadata or Metadata(time_unit="ns")

    @property
    def signals(self):
        return self._signals

    @property
    def metadata(self):
        return self._metadata

    def iter_samples(self):
        for s in self._samples:
            yield s


class TestJSONWriter:
    def test_write_basic(self, tmp_path):
        out = tmp_path / "out.json"
        signals = [Signal("top/clk"), Signal("top/data[7:0]")]
        samples = [
            Sample(0, {"top/clk": "0", "top/data[7:0]": "00"}),
            Sample(1, {"top/clk": "1", "top/data[7:0]": "AB"}),
        ]
        parser = FakeParser(signals, samples)

        writer = JSONWriter(str(out))
        stats = writer.write(parser)

        assert stats["samples"] == 2
        assert stats["signals"] == 2

        data = json.loads(out.read_text())
        assert data["metadata"]["time_unit"] == "ns"
        assert len(data["signals"]) == 2
        assert data["signals"][0]["fullname"] == "top/clk"
        assert data["signals"][0]["width"] == 1
        assert data["samples"][0]["time"] == 0
        assert data["samples"][0]["values"]["top/clk"] == "0"
        assert data["samples"][1]["time"] == 1
        assert data["samples"][1]["values"]["top/data[7:0]"] == "AB"

    def test_write_with_groups(self, tmp_path):
        out = tmp_path / "out.json"
        from gowin2vcd.model import Group
        sig = Signal("top/clk")
        signals = [sig]
        samples = [Sample(0, {"top/clk": "0"})]
        meta = Metadata(groups=[Group(name="clocks", signals=[sig])])
        parser = FakeParser(signals, samples, meta)

        JSONWriter(str(out)).write(parser)
        data = json.loads(out.read_text())
        assert "groups" in data["metadata"]
        assert data["metadata"]["groups"][0]["name"] == "clocks"

    def test_deterministic_output(self, tmp_path):
        out1 = tmp_path / "a.json"
        out2 = tmp_path / "b.json"
        signals = [Signal("clk")]
        samples = [Sample(0, {"clk": "0"})]
        parser = FakeParser(signals, samples)

        JSONWriter(str(out1)).write(parser)
        JSONWriter(str(out2)).write(parser)

        assert json.loads(out1.read_text()) == json.loads(out2.read_text())