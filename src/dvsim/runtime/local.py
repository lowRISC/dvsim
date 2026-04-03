# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Legacy launcher adapter interface for the new async scheduler design."""

import asyncio
import contextlib
import shlex
import signal
import subprocess
import time
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from typing import TextIO

import psutil

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.job.time import JobTime
from dvsim.logging import log
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.data import JobCompletionEvent, JobHandle


@dataclass(kw_only=True)
class LocalJobHandle(JobHandle):
    """Job handle for a job belonging to a legacy launcher adapter runtime backend."""

    process: asyncio.subprocess.Process | None
    log_file: TextIO | None
    start_time: float
    kill_requested: bool = False


class LocalRuntimeBackend(RuntimeBackend):
    """Launch jobs as subprocesses on the user's local machine."""

    name = "local"
    supports_interactive = True

    DEFAULT_SIGTERM_TIMEOUT = 2.0  # in seconds
    DEFAULT_SIGKILL_TIMEOUT = 2.0  # in seconds

    def __init__(
        self,
        *,
        max_parallelism: int | None = None,
        sigterm_timeout: float | None = None,
        sigkill_timeout: float | None = None,
    ) -> None:
        """Construct a local runtime backend.

        Args:
            max_parallelism: The maximum number of jobs that can be dispatched to this backend
              at once. `0` means no limit, `None` means no override is applied to the default.
            sigterm_timeout: The time to wait for a process to die after a SIGTERM when killing
              it, before sending SIGKILL.
            sigkill_timeout: The time to wait for a process to die after a SIGKILL when killing
              it, before giving up (so the scheduler can progress).

        """
        super().__init__(max_parallelism=max_parallelism)
        self.sigterm_timeout = (
            sigterm_timeout if sigterm_timeout is not None else self.DEFAULT_SIGTERM_TIMEOUT
        )
        self.sigkill_timeout = (
            sigkill_timeout if sigkill_timeout is not None else self.DEFAULT_SIGKILL_TIMEOUT
        )

        # Retain references to created asyncio tasks so they don't get GC'd.
        self._tasks: set[asyncio.Task] = set()

    async def _log_from_pipe(
        self, handle: LocalJobHandle, stream: asyncio.StreamReader | None
    ) -> None:
        """Write piped asyncio subprocess stream contents to a job's log file."""
        if stream is None or not handle.log_file:
            return
        try:
            async for line in stream:
                decoded = line.decode("utf-8", errors="surrogateescape")
                handle.log_file.write(decoded)
                handle.log_file.flush()
        except asyncio.CancelledError:
            pass

    async def _monitor_job(self, handle: LocalJobHandle) -> None:
        """Wait for subprocess completion and emit a completion event."""
        if handle.process is None:
            return

        if handle.log_file:
            handle.log_file.write(f"[Executing]:\n{handle.spec.cmd}\n\n")
            handle.log_file.flush()

        reader_tasks = [
            asyncio.create_task(self._log_from_pipe(handle, handle.process.stdout)),
            asyncio.create_task(self._log_from_pipe(handle, handle.process.stderr)),
        ]
        status = JobStatus.KILLED
        reason = None

        try:
            exit_code = await asyncio.wait_for(
                handle.process.wait(), timeout=handle.spec.timeout_secs
            )
            runtime = time.monotonic() - handle.start_time
            status, reason = self._finish_job(handle, exit_code, runtime)
        except asyncio.TimeoutError:
            await self._kill_job(handle)
            status = JobStatus.KILLED
            timeout_message = f"Job timed out after {handle.spec.timeout_mins} minutes"
            reason = JobStatusInfo(message=timeout_message)
        finally:
            # Explicitly cancel reader tasks and wait for them to finish before closing the log
            # file. We first give them a second to finish naturally to reduce log loss.
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait(reader_tasks, timeout=1)
            for task in reader_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*reader_tasks, return_exceptions=True)

            if handle.log_file:
                handle.log_file.close()
            if handle.kill_requested:
                status = JobStatus.KILLED
                reason = JobStatusInfo(message="Job killed!")
            await self._emit_completion([JobCompletionEvent(handle.spec, status, reason)])

    def _launch_interactive_job(
        self,
        job: JobSpec,
        log_file: TextIO | None,
        env: dict[str, str],
    ) -> tuple[LocalJobHandle, JobCompletionEvent | None]:
        """Launch a job in interactive mode with transparent stdin and stdout."""
        start_time = time.monotonic()
        exit_code = None
        completion = None

        if log_file is not None:
            try:
                proc = subprocess.Popen(
                    shlex.split(job.cmd),
                    # Transparent stdin/stdout, stdout & stderr muxed and tee'd via the pipe.
                    stdin=None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    env=env,
                )
                if proc.stdout is not None:
                    for line in proc.stdout:
                        print(line, end="")  # noqa: T201
                        log_file.write(line)
                        log_file.flush()

                exit_code = proc.wait()
            except subprocess.SubprocessError as e:
                log_file.close()
                log.exception("Error launching job subprocess: %s", job.full_name)
                reason = JobStatusInfo(message=f"Failed to launch job: {e}")
                completion = JobCompletionEvent(job, JobStatus.KILLED, reason)

        runtime = time.monotonic() - start_time
        handle = LocalJobHandle(
            spec=job,
            backend=self.name,
            job_runtime=JobTime(),
            simulated_time=JobTime(),
            process=None,
            log_file=log_file,
            start_time=start_time,
        )

        if exit_code is not None:
            status, reason = self._finish_job(handle, exit_code, runtime)
            completion = JobCompletionEvent(job, status, reason)

        return handle, completion

    async def _launch_job(
        self,
        job: JobSpec,
        log_file: TextIO | None,
        env: dict[str, str],
    ) -> tuple[LocalJobHandle | None, JobCompletionEvent | None]:
        """Launch a job (in non-interactive mode) as an async subprocess."""
        proc = None
        completion = None
        if log_file is not None:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *shlex.split(job.cmd),
                    # TODO: currently we mux the stdout and stderr streams by default. It would be
                    # useful to make this behaviour optional on some global `IoPolicy`.
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            except BlockingIOError:
                # Skip this job for now; the scheduler should re-try to launch it later.
                log_file.close()
                return None, None
            except subprocess.SubprocessError as e:
                log_file.close()
                log.exception("Error launching job subprocess: %s", job.full_name)
                reason = JobStatusInfo(message=f"Failed to launch job: {e}")
                completion = JobCompletionEvent(job, JobStatus.KILLED, reason)

        handle = LocalJobHandle(
            spec=job,
            backend=self.name,
            job_runtime=JobTime(),
            simulated_time=JobTime(),
            process=proc,
            log_file=log_file,
            start_time=time.monotonic(),
        )

        # Create a task to asynchronously monitor the launched subprocess.
        # We must store a reference in self._tasks to ensure the task is not GC'd.
        if proc is not None:
            task = asyncio.create_task(self._monitor_job(handle))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        return handle, completion

    async def submit_many(self, jobs: Iterable[JobSpec]) -> dict[Hashable, JobHandle]:
        """Submit & launch multiple jobs.

        Returns:
            mapping from job.id -> JobHandle. Entries are only present for jobs that successfully
            launched; jobs that failed in a non-fatal way are missing, and should be retried.

        """
        completions: list[JobCompletionEvent] = []
        handles: dict[Hashable, JobHandle] = {}

        for job in jobs:
            env = self._build_job_env(job)
            self._prepare_launch(job)

            log_file = None
            try:
                log_file = job.log_path.open("w", encoding="utf-8", errors="surrogateescape")
            except BlockingIOError:
                continue  # Skip this job for now; the scheduler should re-try to launch it later.
            except OSError as e:
                log.exception("Error writing to job log file: %s", job.full_name)
                reason = JobStatusInfo(message=f"Failed to launch job: {e}")
                completions.append(JobCompletionEvent(job, JobStatus.KILLED, reason))

            if job.interactive:
                handle, completion = self._launch_interactive_job(job, log_file, env)
            else:
                handle, completion = await self._launch_job(job, log_file, env)
            if completion is not None:
                completions.append(completion)
            if handle is not None:
                handles[job.id] = handle

        if completions:
            await self._emit_completion(completions)

        return handles

    def _send_kill_signal(self, proc: asyncio.subprocess.Process, signal_num: int) -> None:
        """Send a (kill) signal to a process and all its descendent processes."""
        # TODO: maybe this should use cgroups in the future to be thorough?
        for child in psutil.Process(proc.pid).children(recursive=True):
            child.send_signal(signal_num)
        proc.send_signal(signal_num)

    async def _kill_job(self, handle: LocalJobHandle) -> None:
        """Kill the running local process, sending SIGTERM and then SIGKILL if that didn't work."""
        proc = handle.process
        if proc is None:
            return

        if proc.returncode is None:
            handle.kill_requested = True
            try:
                self._send_kill_signal(proc, signal.SIGTERM)
            except ProcessLookupError:
                return

        try:
            await asyncio.wait_for(proc.wait(), timeout=self.sigterm_timeout)
        except asyncio.TimeoutError:
            pass
        else:
            return

        if proc.returncode is None:
            log.warning(
                "Job '%s' was not killed with SIGTERM after %g seconds, sending SIGKILL.",
                handle.spec.full_name,
                self.sigterm_timeout,
            )
            try:
                self._send_kill_signal(proc, signal.SIGKILL)
            except ProcessLookupError:
                return

            try:
                await asyncio.wait_for(proc.wait(), timeout=self.sigkill_timeout)
            except asyncio.TimeoutError:
                # proc.wait() completes only when the kernel reaps the process. If we sent SIGKILL
                # and did not see this happen for a bit, the process is probably blocked in the
                # kernel somewhere (e.g. NFS hang, slow or dead disk I/O).
                log.error(
                    "Job '%s' was not killed with SIGKILL after %g seconds, so give up on it.",
                    handle.spec.full_name,
                    self.sigkill_timeout,
                )

    async def kill_many(self, handles: Iterable[JobHandle]) -> None:
        """Cancel ongoing jobs via their handle. Killed jobs should still "complete"."""
        tasks = []
        for handle in handles:
            if not isinstance(handle, LocalJobHandle):
                msg = f"Local backend expected handle of type LocalJobHandle, not `{type(handle)}`."
                raise TypeError(msg)
            if handle.process and not handle.kill_requested and handle.process.returncode is None:
                tasks.append(asyncio.create_task(self._kill_job(handle)))

        if tasks:
            # Wait for all job subprocesses to be killed; `_monitor_job` handles the completions.
            await asyncio.gather(*tasks)
