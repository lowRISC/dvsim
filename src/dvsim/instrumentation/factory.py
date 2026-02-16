# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation factory."""

from typing import ClassVar

from dvsim.instrumentation.base import (
    CompositeInstrumentation,
    NoOpInstrumentation,
    SchedulerInstrumentation,
)
from dvsim.instrumentation.metadata import MetadataInstrumentation
from dvsim.instrumentation.resources import ResourceInstrumentation
from dvsim.instrumentation.timing import TimingInstrumentation

__all__ = ("InstrumentationFactory",)


class InstrumentationFactory:
    """Factory/registry for scheduler instrumentation implementations."""

    _registry: ClassVar[dict[str, type[SchedulerInstrumentation]]] = {}

    @classmethod
    def register(cls, name: str, constructor: type[SchedulerInstrumentation]) -> None:
        """Register a new scheduler instrumentation type."""
        cls._registry[name] = constructor

    @classmethod
    def options(cls) -> list[str]:
        """Get a list of available scheduler instrumentation types."""
        return list(cls._registry.keys())

    @classmethod
    def create(cls, names: list[str] | None) -> SchedulerInstrumentation:
        """Create a scheduler instrumentation of the given types.

        Arguments:
            names: A list of registered instrumentation names to compose into a single
            instrumentation object, or None / an empty list for no instrumentation.

        """
        if not names:
            return NoOpInstrumentation()

        instances: list[SchedulerInstrumentation] = [MetadataInstrumentation()]
        instances.extend([cls._registry[name]() for name in names])
        return CompositeInstrumentation(instances)


# Register implemented instrumentation mechanisms
InstrumentationFactory.register("timing", TimingInstrumentation)
InstrumentationFactory.register("resources", ResourceInstrumentation)
