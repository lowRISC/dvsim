# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation report visualization registry."""

from typing import ClassVar

from dvsim.instrumentation.report.base import InstrumentationVisualizer, RenderProfile

__all__ = ("ReportVisualizationRegistry",)


class ReportVisualizationRegistry:
    """Registry for scheduler instrumentation visualizer classes."""

    _registry: ClassVar[dict[str, type[InstrumentationVisualizer]]] = {}

    @classmethod
    def register(cls, vis_cls: type[InstrumentationVisualizer]) -> None:
        """Register a new instrumentation visualization type."""
        cls._registry[vis_cls.title] = vis_cls

    @classmethod
    def clear(cls) -> None:
        """Clear any registered instrumentation visualization types."""
        cls._registry.clear()

    @classmethod
    def registered(cls) -> dict[str, type[InstrumentationVisualizer]]:
        """Get the current state of the registered instrumentation types."""
        return cls._registry.copy()

    @classmethod
    def create(cls, profile: RenderProfile | None = None) -> list[InstrumentationVisualizer]:
        """Create instances of registered visualization types for a given (optional) profile.

        Args:
            profile: The rendering profile (level of detail) to target, if provided.

        Returns:
            A list of InstrumentationVisualizer implementations created for the given profile.

        """
        if profile is None:
            return [vis_cls() for vis_cls in cls._registry.values()]
        return [vis_cls.for_profile(profile) for vis_cls in cls._registry.values()]
