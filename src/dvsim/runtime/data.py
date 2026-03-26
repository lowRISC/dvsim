# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Various dataclasses used by the different runtime backends when executing jobs."""

from collections.abc import Awaitable, Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import TypeAlias

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.job.time import JobTime

__all__ = (
    "CompletionCallback",
    "JobCompletionEvent",
    "JobHandle",
)


@dataclass(kw_only=True)
class JobHandle:
    """A handle for a job that is actively executing on some backend."""

    spec: JobSpec
    backend: str

    # TODO: these are necessary for now because they are exposed in the CompletedJobStatus.
    # It would be nice to figure out a better mechanism for these.
    job_runtime: JobTime
    simulated_time: JobTime

    @property
    def job_id(self) -> Hashable:
        """Returns an object that uniquely identifies the job. Alias of self.spec.id."""
        return self.spec.id


@dataclass(frozen=True)
class JobCompletionEvent:
    """Event emitted when a job finishes."""

    # TODO: ideally we would rather store a `job_id: Hashable` here instead of the full spec, but
    # this is needed to access the `post_finish` callback in `RuntimeBackend._emit_completion`.
    # When these `pre_launch`/`post_finish` callbacks are refactored/removed, this can be changed.
    spec: JobSpec
    """The specification for the job that has been completed."""
    status: JobStatus
    """The terminal/final status of the completed job."""
    reason: JobStatusInfo | None
    """The reason to report as to why the job is in the specified terminal state.
    Typically only reported for non-successful executions, as it is used for e.g. failure message
    buckets - success is implicit.
    """


# Callback (async) for (batches of) job completion events
CompletionCallback: TypeAlias = Callable[[Iterable[JobCompletionEvent]], Awaitable[None]]
