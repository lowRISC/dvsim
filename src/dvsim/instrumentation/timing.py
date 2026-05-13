# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation for timing-related information."""

import time
from collections.abc import Mapping

from dvsim.instrumentation.base import SchedulerInstrumentation
from dvsim.instrumentation.records import JobTimingMetrics, SchedulerTimingMetrics
from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus

__all__ = ("TimingInstrumentation",)


class TimingInstrumentation(SchedulerInstrumentation):
    """Timing instrumentation for the scheduler.

    Collects information about the start time, end time and duration of the scheduler itself and
    all of the jobs that it dispatches.
    """

    name = "timing"

    def __init__(self) -> None:
        """Construct a `TimingInstrumentation`."""
        super().__init__()
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._jobs: dict[str, tuple[float | None, float | None]] = {}

    def on_scheduler_start(self) -> None:
        """Notify instrumentation that the scheduler has begun."""
        self._start_time = time.perf_counter()

    def on_scheduler_end(self) -> None:
        """Notify instrumentation that the scheduler has finished."""
        self._end_time = time.perf_counter()

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify instrumentation of a change in status for some scheduled job."""
        job_info = self._jobs.get(job.id)
        if job_info is None:
            job_info = (None, None)
            self._jobs[job.id] = job_info
        start_time, end_time = job_info

        if start_time is None and status not in (JobStatus.SCHEDULED, JobStatus.QUEUED):
            self._jobs[job.id] = (time.perf_counter(), end_time)
        if status.is_terminal:
            self._jobs[job.id] = (start_time, time.perf_counter())

    def get_scheduler_data(self) -> SchedulerTimingMetrics:
        """Retrieve scheduler metrics measured by this instrumentation."""
        return SchedulerTimingMetrics(start_time=self._start_time, end_time=self._end_time)

    def get_job_data(self) -> Mapping[str, JobTimingMetrics]:
        """Retrieve per-job metrics measured by this instrumentation."""
        return {
            job_id: JobTimingMetrics(start_time=start, end_time=end)
            for job_id, (start, end) in self._jobs.items()
        }
