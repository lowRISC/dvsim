# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation metadata (to be included in the generated report)."""

from dataclasses import dataclass

from dvsim.instrumentation.base import (
    InstrumentationFragments,
    JobFragment,
    SchedulerInstrumentation,
)
from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus

__all__ = (
    "MetadataInstrumentation",
    "MetadataJobFragment",
)


@dataclass
class MetadataJobFragment(JobFragment):
    """Instrumentation metadata for scheduled jobs, reporting the final status of the job."""

    name: str
    full_name: str
    job_type: str
    target: str
    tool: str
    dependencies: list[str]
    status: str


class MetadataInstrumentation(SchedulerInstrumentation):
    """Metadata instrumentation for the scheduler.

    Collects basic metadata about jobs (job spec and status) that are useful to include as
    part of the instrumentation report for analysis, regardless of other instrumentations.
    """

    def __init__(self) -> None:
        """Construct a `MetadataInstrumentation`."""
        super().__init__()
        self._jobs: dict[tuple[str, str], tuple[JobSpec, str]] = {}

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify instrumentation of a change in status for some scheduled job."""
        status_str = status.name.capitalize()
        job_id = (job.full_name, job.target)
        self._jobs[job_id] = (job, status_str)

    def build_report_fragments(self) -> InstrumentationFragments | None:
        """Build report fragments from the collected instrumentation information."""
        jobs = [
            MetadataJobFragment(
                spec,
                spec.name,
                spec.full_name,
                spec.job_type,
                spec.target,
                spec.tool.name,
                spec.dependencies,
                status_str,
            )
            for spec, status_str in self._jobs.values()
        ]
        return ([], jobs)
