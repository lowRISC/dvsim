# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation reporting rendering profiles/levels."""

from enum import Enum


class RenderProfile(Enum):
    """Levels of visualization rendering detail, which impact report size & responsiveness."""

    NORMAL = "normal"
    HIGH = "high"
    FULL = "full"
