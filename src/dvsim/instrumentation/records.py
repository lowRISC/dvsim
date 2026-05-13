# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation output (metric) record models."""

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from dvsim.job.status import JobStatus

__all__ = (
    "ConcreteJobTimingMetrics",
    "InstrumentationMetrics",
    "InstrumentationResults",
    "JobComputeMetrics",
    "JobInstrumentationMetadata",
    "JobInstrumentationResults",
    "JobMetrics",
    "JobTimingMetrics",
    "SchedulerComputeMetrics",
    "SchedulerInstrumentationResults",
    "SchedulerMetrics",
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
    block: str
    block_variant: str | None = None
    backend: str | None = None
    dependencies: list[str]
    status: JobStatus


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


class ConcreteJobTimingMetrics(JobMetrics):
    """Concrete job timing information with all known fields populated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_time: float
    end_time: float
    duration: float


# Compute Resource Metrics


class SchedulerComputeMetrics(SchedulerMetrics):
    """Instrumented compute resource metrics measured for the scheduler as a whole."""

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

    num_samples: int = 0


class JobComputeMetrics(JobMetrics):
    """Instrumented compute resource metrics measured for a single scheduled job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_rss_bytes: int | None = None
    avg_rss_bytes: float | None = None
    avg_cpu_percent: float | None = None

    num_samples: int = 0


# Combined output reports


class SchedulerInstrumentationResults(BaseModel):
    """Aggregated instrumentation report data about the scheduler as a whole."""

    model_config = ConfigDict(frozen=True, extra="allow")

    timing: SchedulerTimingMetrics | None = None
    compute: SchedulerComputeMetrics | None = None


class JobInstrumentationResults(BaseModel):
    """Aggregated instrumentation report data about a single scheduled job."""

    model_config = ConfigDict(frozen=True, extra="allow")

    meta: JobInstrumentationMetadata | None = None
    timing: JobTimingMetrics | None = None
    compute: JobComputeMetrics | None = None


class InstrumentationResults(BaseModel):
    """A complete aggregated instrumentation report with data about the scheduler and all jobs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scheduler: SchedulerInstrumentationResults
    jobs: dict[str, JobInstrumentationResults] = Field(default_factory=dict)

    def job_timings(self) -> dict[str, ConcreteJobTimingMetrics]:
        """Get any complete job timing information that exists in this instrumentation report."""
        return {
            job_id: ConcreteJobTimingMetrics(
                start_time=results.timing.start_time,
                end_time=results.timing.end_time,
                duration=(results.timing.end_time - results.timing.start_time),
            )
            for job_id, results in self.jobs.items()
            if results.timing is not None
            and results.timing.start_time is not None
            and results.timing.end_time is not None
        }

    def get_run_time_info(self) -> tuple[float, float]:
        """Get the run start & end time, falling back to job info if scheduler info is missing."""
        timing = self.scheduler.timing
        if timing is None or timing.start_time is None or timing.end_time is None:
            job_timings = self.job_timings()
            start_time = min((time.start_time for time in job_timings.values()), default=0.0)
            end_time = max((time.end_time for time in job_timings.values()), default=0.0)
            return start_time, end_time
        return timing.start_time, timing.end_time
