"""
JSON waveform export.

Produces a structured JSON dump of the entire capture, useful for:
* automated testing and CI comparisons
* web-based waveform viewers
* debugging parser issues
* feeding into data analysis pipelines
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import Sample
from .model import Signal
from .writers import WaveWriter


class JSONWriter(WaveWriter):
    """Write waveform data as a structured JSON file.

    The output format::

        {
          "metadata": { ... },
          "signals": [
            {"fullname": "...", "width": 1, "hierarchy": [], "basename": "..."}
          ],
          "samples": [
            {"time": 0, "values": {"clk": "0", "rst": "1"}}
          ]
        }
    """

    def __init__(self, filename: str | Path, *, indent: int = 2) -> None:
        self.filename = Path(filename)
        self._indent = indent

    def write(self, parser) -> dict[str, Any]:
        """Write the capture as JSON.

        Returns a dict with conversion statistics.
        """
        start = time.perf_counter()

        # Read metadata
        meta = parser.metadata
        signals = parser.signals

        # Build JSON structure — iterate samples lazily to minimise memory
        metadata_dict = {
            "time_unit": meta.time_unit,
            "radix": meta.radix,
            "clock_name": meta.clock_name,
            "clock_period": meta.clock_period,
        }
        if meta.groups:
            metadata_dict["groups"] = [
                {
                    "name": g.name,
                    "signals": [s.fullname for s in g.signals],
                    "radix": g.radix,
                    "mode": g.mode,
                }
                for g in meta.groups
            ]
        if meta.extra:
            metadata_dict["extra"] = meta.extra

        signals_list = [
            {
                "fullname": s.fullname,
                "width": s.width,
                "hierarchy": list(s.hierarchy),
                "basename": s.basename,
                "alias": s.alias,
            }
            for s in signals
        ]

        # Write header + signals
        header_written = False
        sample_count = 0
        value_changes = 0

        with self.filename.open("w", encoding="utf-8") as fp:
            fp.write("{\n")
            fp.write(f'  "metadata": {json.dumps(metadata_dict, indent=self._indent)},\n')
            fp.write(f'  "signals": {json.dumps(signals_list, indent=self._indent)},\n')
            fp.write('  "samples": [\n')

            first_sample = True
            for sample in parser.iter_samples():
                sample_count += 1
                if not first_sample:
                    fp.write(",\n")
                first_sample = False

                # Count value changes relative to previous
                if sample_count > 1:
                    value_changes += sum(
                        1 for v in sample.values.values() if v
                    )

                sample_dict = {
                    "time": sample.timestamp,
                    "values": dict(sample.values),
                }
                fp.write(json.dumps(sample_dict, indent=self._indent + 2))

            fp.write("\n  ]\n")
            fp.write("}\n")

        elapsed = time.perf_counter() - start
        bytes_written = self.filename.stat().st_size

        return {
            "samples": sample_count,
            "signals": len(signals),
            "value_changes": value_changes,
            "runtime": round(elapsed, 3),
            "bytes_written": bytes_written,
        }