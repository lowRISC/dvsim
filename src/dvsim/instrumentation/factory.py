# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation factory."""

from typing import ClassVar

from dvsim.instrumentation.base import (
    InstrumentationAggregator,
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
    def register(cls, inst_cls: type[SchedulerInstrumentation]) -> None:
        """Register a new scheduler instrumentation type."""
        cls._registry[inst_cls.name] = inst_cls

    @classmethod
    def options(cls) -> list[str]:
        """Get a list of available scheduler instrumentation types."""
        return list(cls._registry.keys())

    @classmethod
    def create(cls, names: list[str]) -> InstrumentationAggregator:
        """Create a scheduler instrumentation of the given types.

        Arguments:
            names: A list of registered instrumentation names.

        """
        if not names:
            raise ValueError("No instrumentation types given")

        instances: list[SchedulerInstrumentation] = [MetadataInstrumentation()]
        instances.extend([cls._registry[name]() for name in names])
        return InstrumentationAggregator(instances)


# Register implemented instrumentation mechanisms
InstrumentationFactory.register(TimingInstrumentation)
InstrumentationFactory.register(ResourceInstrumentation)
