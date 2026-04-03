# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Time-based utilities."""

# Timestamp format when creating directory backups.
TS_FORMAT = "%Y%m%d_%H%M%S"

# Timestamp format when generating reports.
TS_FORMAT_LONG = "%A %B %d %Y %H:%M:%S UTC"


def hms(seconds: float) -> str:
    """Render a duration (in seconds) in the hh:mm:ss format, rounded to the nearest second."""
    total = round(seconds)
    hours, mins = divmod(total, 3600)
    mins //= 60
    secs = total % 60
    return f"{hours:02d}:{mins:02d}:{secs:02d}"
