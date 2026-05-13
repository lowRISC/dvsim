# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation metadata (to be included in the generated report)."""

from collections.abc import Mapping

from dvsim.instrumentation.base import SchedulerInstrumentation
from dvsim.instrumentation.records import JobInstrumentationMetadata
from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus

__all__ = ("MetadataInstrumentation",)


class MetadataInstrumentation(SchedulerInstrumentation):
    """Metadata instrumentation for the scheduler.

    Collects basic metadata about jobs (job spec and status) that are useful to include as
    part of the instrumentation report for analysis, regardless of other instrumentations.
    """

    def __init__(self) -> None:
        """Construct a `MetadataInstrumentation`."""
        super().__init__()
        self._jobs: dict[str, tuple[JobSpec, str]] = {}

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify instrumentation of a change in status for some scheduled job."""
        status_str = status.name.capitalize()
        self._jobs[job.id] = (job, status_str)

    def get_job_data(self) -> Mapping[str, JobInstrumentationMetadata]:
        """Retrieve per-job metrics measured by this instrumentation."""
        return {
            spec.id: JobInstrumentationMetadata(
                name=spec.name,
                job_type=spec.job_type,
                target=spec.target,
                tool=spec.tool.name,
                backend=spec.backend,
                dependencies=list(spec.dependencies),
                status=status_str,
            )
            for spec, status_str in self._jobs.values()
        }
