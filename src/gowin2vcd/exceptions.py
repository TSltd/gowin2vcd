"""
Custom exception hierarchy for gowin2vcd.
"""


class GowinError(Exception):
    """Base exception for all gowin2vcd errors."""


class ParseError(GowinError):
    """Raised when the CSV file cannot be parsed."""


class UnsupportedFormat(GowinError):
    """Raised when the file format is not a recognised GAO variant."""


class EmptyCapture(GowinError):
    """Raised when the capture contains no samples."""


class TimestampOrderError(GowinError):
    """Raised when timestamps are not monotonically increasing."""