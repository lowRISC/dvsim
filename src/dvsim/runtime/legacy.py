# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Legacy launcher adapter interface for the new async scheduler design."""

import asyncio
import time
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.launcher.base import Launcher, LauncherBusyError, LauncherError
from dvsim.logging import log
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.data import JobCompletionEvent, JobHandle


@dataclass(kw_only=True)
class LauncherJobHandle(JobHandle):
    """Job handle for a job belonging to a legacy launcher adapter runtime backend."""

    launcher: Launcher


class LegacyLauncherAdapter(RuntimeBackend):
    """Adapter that allows legacy polling-based launchers to run appearing as a new async backend.

    Each job receives its own legacy launcher instance to account for the fact that launcher
    constructs consume an individual job spec. A single async poll task is used which respects
    the launcher's configured `max_parallel`, `max_polls` and `poll_freq` configuration, to match
    the original scheduler/launcher behaviour more closely.
    """

    name = "legacy"

    def __init__(
        self,
        launcher_cls: type[Launcher],
        *,
        poll_interval: float | None = None,
        max_polls_per_interval: int | None = None,
        max_parallelism: int | None = None,
    ) -> None:
        """Construct a legacy launcher adapter.

        Args:
            launcher_cls: The legacy launcher class to adapt as a backend.
            poll_interval: Override for the interval (seconds) between poll attempts.
            max_polls_per_interval: The maximum number of jobs that can be polled in a single
               interval. `0` means no limit, `None` means no override is applied to the default.
            max_parallelism: The maximum number of jobs that can be dispatched to this backend
              at once. `0` means no limit, `None` means no override is applied to the default.

        """
        if max_parallelism is None:
            max_parallelism = launcher_cls.max_parallel
        super().__init__(max_parallelism=max_parallelism)

        self.launcher_cls = launcher_cls

        # Get the name from the defined variant, or from the class name, or just "legacy".
        if launcher_cls.variant is not None:
            self.name = launcher_cls.variant
        else:
            name = launcher_cls.__name__.lower()
            if name.endswith("launcher"):
                self.name = name.removesuffix("launcher")

        self.poll_interval = poll_interval if poll_interval is not None else launcher_cls.poll_freq
        self.max_polls_per_interval = (
            max_polls_per_interval if max_polls_per_interval is not None else launcher_cls.max_poll
        )
        # This is just hardcoded for now; from inspection, it seems these two launchers are
        # the only ones that actually support interactivity.
        self.supports_interactive = self.name in ("local", "nc")

        # Track launchers that have been created but not yet launched due to LauncherBusyErrors.
        self._pending_launchers: dict[Hashable, Launcher] = {}

        # FIFO Queue defining the order in which jobs should be polled.
        self._poll_queue: list[LauncherJobHandle] = []

        self._poller_task: asyncio.Task | None = None
        self._closed: bool = False

    def _ensure_poller(self) -> None:
        """Lazily make sure that a poller task exists."""
        if self._poller_task is None:
            log.warning("Using legacy runtime adapter for the '%s' launcher.", self.name)
            log.warning("Consider rewriting the launcher as a runtime backend if needed.")
            self._poller_task = asyncio.create_task(self._poller())

    def _extract_launcher_job_failure(
        self, status: JobStatus, handle: LauncherJobHandle
    ) -> JobStatusInfo | None:
        """Extract relevant information about a job failure within a launcher."""
        if status not in (JobStatus.FAILED, JobStatus.KILLED):
            return None
        fail_msg = handle.launcher.fail_msg
        if fail_msg is None or not fail_msg.message:
            return None

        return JobStatusInfo(
            message=fail_msg.message,
            lines=[fail_msg.line_number] if fail_msg.line_number is not None else None,
            context=fail_msg.context,
        )

    async def _poller(self) -> None:
        """Poll all dispatched legacy jobs in a serial polling loop."""
        next_tick = time.monotonic() + self.poll_interval
        try:
            while not self._closed:
                completions: list[JobCompletionEvent] = []

                if self.max_polls_per_interval:
                    handles_to_poll = self._poll_queue[: self.max_polls_per_interval]
                    self._poll_queue = self._poll_queue[len(handles_to_poll) :]
                else:
                    handles_to_poll = self._poll_queue.copy()
                    self._poll_queue.clear()

                for handle in handles_to_poll:
                    try:
                        status = handle.launcher.poll()
                    except LauncherError as e:
                        log.error("Error when polling job: %s", str(e))
                        status = JobStatus.KILLED
                    if status.is_terminal:
                        reason = self._extract_launcher_job_failure(status, handle)
                        completion_event = JobCompletionEvent(handle.spec, status, reason)
                        completions.append(completion_event)
                    else:
                        self._poll_queue.append(handle)

                if completions:
                    await self._emit_completion(completions)

                now = time.monotonic()
                sleep_time = max(0, next_tick - now)
                next_tick += self.poll_interval
                await asyncio.sleep(sleep_time)
        finally:
            self._poller_task = None

    async def submit_many(self, jobs: Iterable[JobSpec]) -> dict[Hashable, JobHandle]:
        """Submit & launch multiple jobs via Launchers.

        Returns:
            mapping from job.id -> JobHandle. Entries are only present for jobs that successfully
            launched; jobs that failed in a non-fatal way are missing, and should be retried.

        """
        self._ensure_poller()

        handles: dict[Hashable, JobHandle] = {}
        completions: list[JobCompletionEvent] = []  # For jobs with errors during launching

        for job in jobs:
            # For the sake of wrapping and maintaining existing functionality, we do not
            # prepare the build env vars or output directories here. That is done in the
            # launcher itself to support these legacy implementations.
            if job.id in self._pending_launchers:
                launcher = self._pending_launchers[job.id]
            else:
                launcher = self.launcher_cls(job)
                self._pending_launchers[job.id] = launcher

            try:
                launcher.launch()
            except LauncherError as e:
                log.exception("Error launching %s", job.full_name)
                reason = JobStatusInfo(message=f"Error launching job: {e}")
                completions.append(JobCompletionEvent(job, JobStatus.KILLED, reason))
            except LauncherBusyError:
                log.exception("Legacy '%s' launcher is busy", self.name)
                continue

            self._pending_launchers.pop(job.id, None)
            handle = LauncherJobHandle(
                spec=job,
                backend=self.name,
                job_runtime=launcher.job_runtime,
                simulated_time=launcher.simulated_time,
                launcher=launcher,
            )
            self._poll_queue.append(handle)
            handles[job.id] = handle

        if completions:
            await self._emit_completion(completions)

        return handles

    async def kill_many(self, handles: Iterable[JobHandle]) -> None:
        """Cancel ongoing jobs via their handle. Killed jobs should still "complete"."""
        completions: list[JobCompletionEvent] = []

        for handle in handles:
            if not isinstance(handle, LauncherJobHandle):
                type_ = "LauncherJobHandle"
                msg = f"Legacy backend expected handle of type `{type_}`, not `{type(handle)}`."
                raise TypeError(msg)

            handle.launcher.kill()
            completion = JobCompletionEvent(handle.spec, JobStatus.KILLED, None)
            completions.append(completion)
            if handle in self._poll_queue:
                self._poll_queue.remove(handle)

        if completions:
            await self._emit_completion(completions)

    async def close(self) -> None:
        """Release any resources that the backend holds; called when the scheduler completes.

        Ensures that the dedicated asyncio poller task is cancelled.

        """
        self._closed = True
        if self._poller_task:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError as e:
                log.debug("Ignoring asyncio cancellation error: %s", str(e))
            self._poller_task = None
