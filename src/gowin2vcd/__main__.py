"""
Entry point for ``python -m gowin2vcd``.
"""

from __future__ import annotations

import sys

from .cli import main

sys.exit(main())