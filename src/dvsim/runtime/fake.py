# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Fake runtime backend that returns random results."""

from collections.abc import Callable, Hashable, Iterable
from typing import TypeAlias

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.job.time import JobTime
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.data import JobCompletionEvent, JobHandle

# Callback for the job faking policy, to tell the fake backend how it should fake jobs.
# Returns the faked status.
FakePolicy: TypeAlias = Callable[[JobSpec], JobStatus]


class FakeRuntimeBackend(RuntimeBackend):
    """Backend that instantly generates and returns random faked results."""

    name = "fake"

    def __init__(
        self, *, policy: FakePolicy | None = None, max_parallelism: int | None = None
    ) -> None:
        """Construct a fake runtime backend."""
        super().__init__(max_parallelism=max_parallelism)

        self._fake_policy = policy or self._default_fake

    def _default_fake(self, _job: JobSpec) -> JobStatus:
        """If not told how to fake, this backend will always pass every job."""
        return JobStatus.PASSED

    def attach_fake_policy(self, policy: FakePolicy) -> None:
        """Register a new faking policy via a callback."""
        self._fake_policy = policy

    async def submit_many(self, jobs: Iterable[JobSpec]) -> dict[Hashable, JobHandle]:
        """Submit & launch multiple jobs.

        Returns:
            mapping from job.id -> JobHandle. Entries are only present for jobs that successfully
            launched; jobs that failed in a non-fatal way are missing, and should be retried.

        """
        handles: dict[Hashable, JobHandle] = {}
        completions: list[JobCompletionEvent] = []

        for job in jobs:
            status = self._fake_policy(job)
            if not status.is_terminal:
                msg = (
                    "Fake runtime backend currently does not handle non-terminal status "
                    + status.name.capitalize()
                )
                raise RuntimeError(msg)
            reason = JobStatusInfo(message="Fake result")
            completions.append(JobCompletionEvent(job, status, reason))
            handles[job.id] = JobHandle(
                spec=job, backend=self.name, job_runtime=JobTime(), simulated_time=JobTime()
            )

        if completions:
            await self._emit_completion(completions)

        return handles

    async def kill_many(self, handles: Iterable[JobHandle]) -> None:
        """Cancel ongoing jobs via their handle. Killed jobs should still "complete"."""
        # We already emitted a fake completion event for all jobs, so no need to do anything
