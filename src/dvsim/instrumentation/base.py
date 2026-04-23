# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation base classes."""

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, TypeAlias

from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.scheduler.core import Scheduler

__all__ = (
    "InstrumentationAggregator",
    "InstrumentationFragment",
    "InstrumentationFragments",
    "JobFragment",
    "SchedulerFragment",
    "SchedulerInstrumentation",
)


@dataclass
class InstrumentationFragment:
    """Base class for instrumentation reports / report fragments."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the report fragment to a dictionary."""
        return asdict(self)


@dataclass
class SchedulerFragment(InstrumentationFragment):
    """Base class for instrumentation report fragments related to the scheduler."""


@dataclass
class JobFragment(InstrumentationFragment):
    """Base class for instrumentation report fragments related to individual jobs."""

    job: JobSpec


# Each instrumentation object can report any number of information fragments about the
# scheduler and about its jobs.
InstrumentationFragments: TypeAlias = tuple[Sequence[SchedulerFragment], Sequence[JobFragment]]


class SchedulerInstrumentation:
    """Instrumentation for the scheduler.

    Base class for scheduler instrumentation, recording a variety of performance and
    behavioural metrics for analysis.
    """

    @property
    def name(self) -> str:
        """The name to use to refer to this instrumentation mechanism."""
        return self.__class__.__name__

    def start(self) -> None:
        """Begin instrumentation, starting whatever is needed before the scheduler is run."""
        log.info("Starting instrumentation: %s", self.name)
        self._start()

    def _start(self) -> None:
        return None

    def stop(self) -> None:
        """Stop instrumentation, ending any instrumentation-specific resources."""
        log.info("Stopping instrumentation: %s", self.name)
        self._stop()

    def _stop(self) -> None:
        return None

    def on_scheduler_start(self) -> None:
        """Notify instrumentation that the scheduler has begun."""
        return

    def on_scheduler_end(self) -> None:
        """Notify instrumentation that the scheduler has finished."""
        return

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:  # noqa: ARG002
        """Notify instrumentation of a change in status for some scheduled job."""
        return

    def build_report_fragments(self) -> InstrumentationFragments | None:
        """Build report fragments from the collected instrumentation information."""
        return None


class InstrumentationAggregator:
    """Aggregator for scheduler instrumentation collection, composing multiple instrumentations."""

    def __init__(self, instrumentations: Iterable[SchedulerInstrumentation]) -> None:
        """Construct an InstrumentationAggregator to compose the given instrumentations."""
        self._instrumentations = list(instrumentations)

    def setup(self, scheduler: Scheduler) -> None:
        """Set up instrumentation, sending start signals & registering scheduler callbacks."""
        for inst in self._instrumentations:
            inst.start()

            # Add instrumentation hooks
            scheduler.add_run_start_callback(inst.on_scheduler_start)
            scheduler.add_run_end_callback(inst.on_scheduler_end)
            scheduler.add_job_status_change_callback(
                lambda spec, _old, new, inst=inst: inst.on_job_status_change(spec, new)
            )

    def stop(self) -> None:
        """Finish instrumentation, closing all relevant resources."""
        for inst in self._instrumentations:
            inst.stop()

    def collect(self) -> dict[str, Any]:
        """Collect all gathered instrumentation data from the wrapped objects."""
        log.info("Collecting instrumentation data...")

        scheduler_fragments = []
        job_fragments = []

        for inst in self._instrumentations:
            fragments = inst.build_report_fragments()
            if fragments is None:
                continue
            scheduler_fragments += fragments[0]
            job_fragments += fragments[1]

        log.info("Finished collecting instrumentation data. Merging instrumentation data...")

        scheduler: dict[str, Any] = {}
        for i, scheduler_frag in enumerate(scheduler_fragments, start=1):
            log.debug(
                "Merging instrumentation report scheduler data (%d/%d)", i, len(scheduler_fragments)
            )
            scheduler.update(scheduler_frag.to_dict())

        jobs: dict[tuple[str, str], dict[str, Any]] = {}
        for i, job_frag in enumerate(job_fragments, start=1):
            log.debug("Merging instrumentation report job data (%d/%d)", i, len(job_fragments))
            spec = job_frag.job
            # We can uniquely identify jobs from the combination of their full name & target
            job_id = (spec.full_name, spec.target)
            job = jobs.get(job_id)
            if job is None:
                job = {}
                jobs[job_id] = job
            job.update({k: v for k, v in job_frag.to_dict().items() if k != "job"})

        log.info("Finished merging instrumentation report data.")
        return {"scheduler": scheduler, "jobs": list(jobs.values())}
