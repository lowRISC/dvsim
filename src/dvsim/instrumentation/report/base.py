# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation reporting & visualizations."""

from enum import Enum
from typing import Protocol

from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.logging import log

__all__ = (
    "InstrumentationVisualizer",
    "RenderProfile",
)


class RenderProfile(Enum):
    """Levels of visualization rendering detail, which impact report size & responsiveness."""

    NORMAL = "normal"
    HIGH = "high"
    FULL = "full"


class InstrumentationVisualizer(Protocol):
    """Builder & renderer for HTML instrumentation visualizations."""

    # A short name / title of the visualization, used in the HTML report navigation tab
    title: str

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a visualization from the instrumentation results as a HTML fragment.

        If the required data is not provide in the instrumentation results (e.g. not enough
        data, or not the correct type of data recorded), or the visualization should not be
        generated, this can also optionally return `None`.

        """
        ...

    @classmethod
    def for_profile(cls, profile: RenderProfile) -> Self:
        """Create a visualizer instance configured for a given rendering profile (if supported)."""
        log.debug("Render profile %s not used by visualization '%s'", profile.name, cls.title)
        return cls()
