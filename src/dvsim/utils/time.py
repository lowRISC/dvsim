# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Time-based utilities and common formats."""

# Timestamp format when creating directory backups.
TS_FORMAT = "%Y%m%d_%H%M%S"

# Timestamp format when generating reports.
TS_FORMAT_LONG = "%A %B %d %Y %H:%M:%S UTC"

# Timestamp format for Hours:Minutes:Seconds display as used by the scheduler
TS_HMS_FORMAT = "%H:%M:%S"


def format_time_as_hms(seconds: float, *, decimals: int = 2, omit_zero: bool = False) -> str:
    """Format a time in seconds like '12h 34m 56.79s'.

    Args:
        seconds: The time in seconds to format.
        decimals: The number of decimal places to use for non-integer seconds (default 2).
        omit_zero: True if zero fields (e.g. '0h 0m') should be omitted, false otherwise.

    Returns:
        A formatted time string.

    """
    if seconds < 0:
        msg = f"Cannot format negative time value: {seconds}s"
        raise ValueError(msg)

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    hms = f"{secs:.{decimals}f}s"
    if minutes > 0 or hours > 0 or not omit_zero:
        hms = f"{int(minutes)}m " + hms
    if hours > 0 or not omit_zero:
        hms = f"{int(hours)}h " + hms
    return hms


def format_time_metric(
    seconds: float, *, hms_decimals: int = 2, second_decimals: int = 2, omit_zero: bool = False
) -> str:
    """Return a time metric formatted as e.g. '2h 15m 37.21s (8,137.21s)'.

    Args:
        seconds: The time in seconds to format.
        hms_decimals: The number of decimal places to use for the 'Xh Ym Zs' output.
        second_decimals: The number of decimal places to use for the '(Xs)' output.
        omit_zero: True if zero fields (e.g. '0h 0m') should be omitted, false otherwise.

    Returns:
        A formatted string for the given time metric value.

    """
    hms = format_time_as_hms(seconds, decimals=hms_decimals, omit_zero=omit_zero)
    return f"{hms} ({seconds:,.{second_decimals}f}s)"
