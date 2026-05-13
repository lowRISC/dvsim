# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation output (metric) record models."""

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
    model_validator,
)

__all__ = (
    "InstrumentationMetrics",
    "JobInstrumentationMetadata",
    "JobMetrics",
    "JobResourceMetrics",
    "JobTimingMetrics",
    "SchedulerMetrics",
    "SchedulerResourceMetrics",
    "SchedulerTimingMetrics",
)

# Base model classes


class InstrumentationMetrics(BaseModel):
    """Base class for instrumentation metrics (report fragments)."""


class SchedulerMetrics(InstrumentationMetrics):
    """Base class for instrumentation metrics related to the scheduler as a whole."""


class JobMetrics(InstrumentationMetrics):
    """Base class for instrumentation metrics related to a specific job."""


class JobInstrumentationMetadata(JobMetrics):
    """Instrumented metadata captured for a single scheduled job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    job_type: str
    target: str
    tool: str
    backend: str | None
    dependencies: list[str]
    status: str


# Timing metrics


class SchedulerTimingMetrics(SchedulerMetrics):
    """Instrumented timing metrics measured for the scheduler as a whole."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    start_time: float | None = None
    end_time: float | None = None

    @computed_field
    @property
    def duration(self) -> float | None:
        """The duration of the entire scheduler run."""
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time

    @model_validator(mode="before")
    @classmethod
    def drop_computed_fields(cls, data: Any) -> Any:  # noqa: ANN401
        """Drop any computed fields from input dicts before validating."""
        if isinstance(data, dict):
            data = dict(data)
            data.pop("duration", None)
        return data


class JobTimingMetrics(JobMetrics):
    """Instrumented timing metrics measured for a single scheduled job."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    start_time: float | None = None
    end_time: float | None = None

    @computed_field
    @property
    def duration(self) -> float | None:
        """The duration of the entire job run."""
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time

    @model_validator(mode="before")
    @classmethod
    def drop_computed_fields(cls, data: Any) -> Any:  # noqa: ANN401
        """Drop any computed fields from input dicts before validating."""
        if isinstance(data, dict):
            data = dict(data)
            data.pop("duration", None)
        return data


# Resource Metrics


class SchedulerResourceMetrics(SchedulerMetrics):
    """Instrumented resource metrics measured for the scheduler as a whole."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Scheduler / DVSim process overhead
    scheduler_max_rss_bytes: int | None = None
    scheduler_avg_rss_bytes: int | None = None
    scheduler_vms_bytes: int | None = None
    scheduler_cpu_percent: float | None = None
    scheduler_cpu_time: float | None = None

    # System-wide metrics
    sys_max_rss_bytes: int | None = None
    sys_avg_rss_bytes: int | None = None
    sys_swap_used_bytes: int | None = None
    sys_cpu_percent: float | None = None
    sys_cpu_per_core: list[float] | None = None

    num_resource_samples: int = 0


class JobResourceMetrics(JobMetrics):
    """Instrumented resource metrics measured for a single scheduled job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_rss_bytes: int | None = None
    avg_rss_bytes: float | None = None
    avg_cpu_percent: float | None = None

    num_resource_samples: int = 0
