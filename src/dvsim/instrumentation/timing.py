# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation for timing-related information."""

import time
from dataclasses import asdict, dataclass
from typing import Any

from dvsim.instrumentation.base import (
    InstrumentationFragments,
    JobFragment,
    SchedulerFragment,
    SchedulerInstrumentation,
)
from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus

__all__ = (
    "TimingInstrumentation",
    "TimingJobFragment",
    "TimingSchedulerFragment",
)


@dataclass
class TimingSchedulerFragment(SchedulerFragment):
    """Instrumented metrics about the scheduler reported by the `TimingInstrumentation`."""

    start_time: float | None = None
    end_time: float | None = None

    @property
    def duration(self) -> float | None:
        """The duration of the entire scheduler run."""
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert the scheduler metrics to a dictionary, including the `duration` property."""
        data = asdict(self)
        duration = self.duration
        if duration:
            data["duration"] = duration
        return data


@dataclass
class TimingJobFragment(JobFragment):
    """Instrumented metrics about the scheduler reported by the `TimingInstrumentation`."""

    start_time: float | None = None
    end_time: float | None = None

    @property
    def duration(self) -> float | None:
        """The duration of the job."""
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert the job metrics to a dictionary, including the `duration` property."""
        data = asdict(self)
        duration = self.duration
        if duration:
            data["duration"] = duration
        return data


class TimingInstrumentation(SchedulerInstrumentation):
    """Timing instrumentation for the scheduler.

    Collects information about the start time, end time and duration of the scheduler itself and
    all of the jobs that it dispatches.
    """

    def __init__(self) -> None:
        """Construct a `TimingInstrumentation`."""
        super().__init__()
        self._scheduler = TimingSchedulerFragment()
        self._jobs: dict[tuple[str, str], TimingJobFragment] = {}

    def on_scheduler_start(self) -> None:
        """Notify instrumentation that the scheduler has begun."""
        self._scheduler.start_time = time.time()

    def on_scheduler_end(self) -> None:
        """Notify instrumentation that the scheduler has finished."""
        self._scheduler.end_time = time.time()

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify instrumentation of a change in status for some scheduled job."""
        job_id = (job.full_name, job.target)
        job_info = self._jobs.get(job_id)
        if job_info is None:
            job_info = TimingJobFragment(job)
            self._jobs[job_id] = job_info

        if job_info.start_time is None and status != JobStatus.QUEUED:
            job_info.start_time = time.time()
        if status.ended:
            job_info.end_time = time.time()

    def build_report_fragments(self) -> InstrumentationFragments | None:
        """Build report fragments from the collected instrumentation information."""
        return ([self._scheduler], list(self._jobs.values()))
