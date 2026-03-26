# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Runtime backend abstract base class."""

from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable

from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.runtime.data import (
    CompletionCallback,
    JobCompletionEvent,
    JobHandle,
)


class RuntimeBackend(ABC):
    """Abstraction for a backend that launches, maintains, polls and kills a job.

    Provides methods to prepare an environment for running a job, launching the job,
    polling for its completion, killing it, and doing some cleanup activities.
    """

    name: str
    """The name of the backend."""

    max_parallelism: int = 0
    """The maximum number of jobs that can be run at any time via this backend. The scheduler
    should respect the parallelism limit defined here.
    """

    max_output_dirs: int = 5
    """If a history of previous invocations is to be maintained, keep at most this many dirs."""

    supports_interactive: bool = False
    """Whether this backend supports jobs in interactive mode (transparent stdin/stdout)."""

    def __init__(self, *, max_parallelism: int | None = None) -> None:
        """Construct a runtime backend.

        Args:
            max_parallelism: The maximum number of jobs that can be dispatched to this backend
            at once. `0` means no limit, `None` means no override is applied to the default.

        """
        if max_parallelism is not None:
            self.max_parallelism = max_parallelism

        self._completion_callback: CompletionCallback | None = None

    def attach_completion_callback(self, callback: CompletionCallback) -> None:
        """Attach a callback for completed events, to notify the scheduler.

        Args:
            callback: the callback to use for job completion events.

        """
        self._completion_callback = callback

    async def _emit_completion(self, events: Iterable[JobCompletionEvent]) -> None:
        """Mark a job as now being in some completed/terminal state by notifying the scheduler."""
        if self._completion_callback is None:
            raise RuntimeError("Backend not attached to the scheduler")

        for event in events:
            log.debug(
                "Job %s completed execution: %s", event.spec.qual_name, event.status.shorthand
            )
            if event.status != JobStatus.PASSED and event.reason is not None:
                log.verbose(
                    "Job %s has status '%s' instead of 'Passed'. Reason: %s",
                    event.spec.qual_name,
                    event.status.name.capitalize(),
                    event.reason.message,
                )

        await self._completion_callback(events)

    @abstractmethod
    async def submit_many(self, jobs: Iterable[JobSpec]) -> dict[Hashable, JobHandle]:
        """Submit & launch multiple jobs.

        Returns:
            mapping from job.id -> JobHandle. Entries are only present for jobs that successfully
            launched; jobs that failed in a non-fatal way are missing, and should be retried.

        """

    async def submit(self, job: JobSpec) -> JobHandle | None:
        """Submit & launch a job, returning a handle for that job.

        If the job failed to launch in a non-fatal way (e.g. backend is busy), None is returned
        instead, and the job should be re-submitted at some later time.
        """
        result = await self.submit_many([job])
        return result.get(job.id)

    @abstractmethod
    async def kill_many(self, handles: Iterable[JobHandle]) -> None:
        """Cancel ongoing jobs via their handle. Killed jobs should still "complete"."""

    async def kill(self, handle: JobHandle) -> None:
        """Cancel an ongoing job via its handle. Killed jobs should still "complete"."""
        await self.kill_many([handle])

    async def close(self) -> None:  # noqa: B027
        """Release any resources that the backend holds; called when the scheduler completes.

        The default implementation just does nothing.

        """
