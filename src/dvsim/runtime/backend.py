# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Runtime backend abstract base class."""

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable, Sequence
from pathlib import Path

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.job.time import JobTime
from dvsim.logging import log
from dvsim.runtime.data import (
    CompletionCallback,
    JobCompletionEvent,
    JobHandle,
)
from dvsim.tool.utils import get_sim_tool_plugin
from dvsim.utils import clean_odirs

__all__ = ("RuntimeBackend",)

# A list of magic flags that are currently cleared.
# TODO: it would be good to find a nicer solution for this - perhaps a common configuration
# could just re-export it or define that it should not exist? Or it could be in a DVSim config.
MAGIC_VARS_TO_CLEAR = {
    # This variable is used by recursive Make calls to pass variables from one level to the next.
    # Even if our command here invokes Make, it should logically be a top-level invocation. We
    # don't want to pollute the flow with Make variables from any wrapper that called DVSim.
    "MAKEFLAGS",
}

# Relative paths to files created in job output directories
ENV_DUMP_PATH = "env_vars"


# The number of lines to give as context when a failure pattern is parsed from a log file.
NUM_LOG_FAIL_CONTEXT_LINES = 4
# The number of lines to give as context when pass patterns are missing from a log file.
NUM_LOG_PASS_CONTEXT_LINES = 10
# The number of lines to give as context when a non-zero exit code is returned.
NUM_RETCODE_CONTEXT_LINES = 10


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
            # TODO: aim to refactor to remove these callbacks
            event.spec.post_finish(event.status)

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

    def _build_job_env(
        self,
        job: JobSpec,
        backend_env: dict[str, str] | None = None,
        remove: Iterable[str] | None = None,
    ) -> dict[str, str]:
        """Build job environment configuration for a given job.

        Arguments:
            job: The job specification to get the environment from.
            context: The job execution context for this backend.
            backend_env: Any backend-specific environment overrides to use. Defaults to None.
              Takes precedence over the base OS environment, but is overridden by the job itself.
            remove: A list of variables to remove from the final environment variable list.
              Defaults to None.

        Returns the job environment as a mapping of env var names to values.

        """
        # Take the existing environment variables and update with any exports defined on the spec.
        # TODO: consider adding some `--clean-env` CLI arg & flag to only use `job.exports` instead
        # of also inheriting from `os.environ`?
        env = dict(os.environ)
        if backend_env:
            env.update(backend_env)
        env.update(job.exports)

        # If the job is set to run in "interactive" mode, we set the `RUN_INTERACTIVE` environment
        # variable to 1, and also make a note in the environment.
        if job.interactive:
            env["DVSIM_RUN_INTERACTIVE"] = "1"
            # TODO: Legacy environment variable not prefixed with `DVSIM` - deprecate this.
            env["RUN_INTERACTIVE"] = "1"

        # Clear any magic flags or `remove` entries from the environment variable export list
        for key in remove or ():
            env.pop(key, None)
        for magic_var in MAGIC_VARS_TO_CLEAR:
            env.pop(magic_var, None)

        # Dump the environment variables to their own file to make debugging easier.
        if job.odir and job.odir.exists():
            dump = job.odir / ENV_DUMP_PATH
            with dump.open("w", encoding="utf-8", errors="surrogateescape") as f:
                f.writelines(f"{key}={value}\n" for key, value in sorted(env.items()))

        return env

    def _make_job_output_directory(self, job: JobSpec) -> None:
        """Create the output directory for a job.

        Depending on the configured `renew_odir` setting, this will optionally clean or maintain
        a list of previous output directories for this job.

        """
        if job.renew_odir:
            clean_odirs(odir=job.odir, max_odirs=self.max_output_dirs)

        Path(job.odir).mkdir(exist_ok=True, parents=True)

    def _prepare_launch(self, job: JobSpec) -> None:
        """Do any pre-launch activities, preparing the environment.

        This may include clearing old runs, creating the output directory, etc.
        """
        if job.interactive and not self.supports_interactive:
            msg = f"Interactive jobs are not supported by the '{self.name}' backend."
            raise RuntimeError(msg)

        job.pre_launch()
        self._make_job_output_directory(job)

    def _finish_job(
        self, handle: JobHandle, exit_code: int, runtime: float | None
    ) -> tuple[JobStatus, JobStatusInfo | None]:
        """Determine the outcome of a job that ran to completion, and parse extra log info.

        Updates the handle with any extracted job runtime & simulation time info.
        """
        if handle.spec.dry_run:
            return JobStatus.PASSED, None

        log_results = LogResults(handle.spec)

        # Update time information on the handle.
        job_runtime, simulated_time = log_results.get_runtime_from_logs()
        if job_runtime is None:
            log.warning("%s: Using dvsim-maintained job_runtime instead.", handle.spec.full_name)
            if runtime is not None:
                handle.job_runtime.set(runtime, "s")
        else:
            handle.job_runtime.set(*job_runtime.get())
        if simulated_time is not None:
            handle.simulated_time.set(*simulated_time.get())

        # Determine the final status from the logs and exit code.
        status, reason = log_results.get_status_from_logs()
        if status is not None:
            return status, reason
        if exit_code != 0:
            lines = log_results.get_lines()
            return JobStatus.FAILED, JobStatusInfo(
                message=f"Job returned a non-zero exit code: {exit_code}",
                context=lines[-NUM_RETCODE_CONTEXT_LINES:],
            )
        return JobStatus.PASSED, None


class LogResults:
    """Wrapper for log result parsing which lazily loads the contents of the job log file."""

    def __init__(self, job: JobSpec) -> None:
        """Construct a LogResults object. Does not load the log file until needed."""
        self.spec = job
        self._parsed = False
        self._lines: list[str] | None = None
        self._err_status: tuple[JobStatus, JobStatusInfo] | None = None

    def _ensure_log_parsed(self) -> None:
        """Parse the log file into its lines if not already parsed."""
        if self._parsed:
            return

        try:
            with self.spec.log_path.open(encoding="utf-8", errors="surrogateescape") as f:
                self._lines = f.readlines()
        except OSError as e:
            log.debug(
                "%s: Error reading job log file %s: %s",
                self.spec.full_name,
                str(self.spec.log_path),
                str(e),
            )
            self._err_status = (
                JobStatus.FAILED,
                JobStatusInfo(message=f"Error opening file {self.spec.log_path}:\n{e}"),
            )
        finally:
            self._parsed = True

    def get_lines(self) -> Sequence[str]:
        """Get the sequence of lines in the log results, or an empty sequence if failed parsing."""
        self._ensure_log_parsed()
        return () if self._lines is None else self._lines

    def get_status_from_logs(self) -> tuple[JobStatus | None, JobStatusInfo | None]:
        """Determine the outcome of a completed job from its log file."""
        # Check we actually need to use the logs before loading them
        use_log_check_strategy = bool(self.spec.fail_patterns) or bool(self.spec.pass_patterns)
        if not use_log_check_strategy:
            return None, None

        lines = self.get_lines()
        if self._err_status:
            return self._err_status

        fail_regex = None
        if self.spec.fail_patterns:
            fail_regex = re.compile("|".join(f"(?:{p})" for p in self.spec.fail_patterns))
        pass_regexes = {re.compile(pattern) for pattern in self.spec.pass_patterns}

        # TODO: does this need to be restricted to per-line patterns? It would complicate line
        # number parsing, but it might be useful to make this more expressive?
        for lineno, line in enumerate(lines, start=1):
            # If the job matches ANY fail pattern, it fails. Provide some extra lines for context.
            if fail_regex and fail_regex.search(line):
                end = lineno + NUM_LOG_FAIL_CONTEXT_LINES
                return JobStatus.FAILED, JobStatusInfo(
                    message=line.strip(), lines=[lineno], context=lines[lineno:end]
                )

            # The job must match ALL pass patterns to succeed.
            matched = {regex for regex in pass_regexes if regex.search(line)}
            pass_regexes -= matched

            if not pass_regexes and not fail_regex:
                break  # Early exit if possible

        if pass_regexes:
            pass_patterns = [regex.pattern for regex in pass_regexes]
            return JobStatus.FAILED, JobStatusInfo(
                message=f"Some pass patterns missing: {pass_patterns}",
                context=lines[-NUM_LOG_PASS_CONTEXT_LINES:],
            )

        return None, None

    def get_runtime_from_logs(self) -> tuple[JobTime | None, JobTime | None]:
        """Try to determine a job's runtime from its log file, using specified extensions."""
        # TODO: rather than check the job type here, in the future the sim tool plugin should
        # define the job types it supports. Even longer term, perhaps the job time and sim time
        # should not be defined on the JobHandle/CompletedJobStatus and should be directly parsed
        # out of the resulting log artifacts by the respective flows.
        sim_job_types = ["CompileSim", "RunTest", "CovUnr", "CovMerge", "CovReport", "CovAnalyze"]
        supports_log_info_ext = self.spec.job_type in sim_job_types
        if not supports_log_info_ext:
            return None, None

        lines = self.get_lines()
        if self._err_status:
            return None, None

        try:
            plugin = get_sim_tool_plugin(tool=self.spec.tool.name)
        except NotImplementedError as e:
            log.error("%s: %s", self.spec.full_name, str(e))
            return None, None

        runtime = None
        try:
            time, unit = plugin.get_job_runtime(self.spec, log_text=lines)
            runtime = JobTime(time, unit)
        except RuntimeError as e:
            log.warning("%s: %s", self.spec.full_name, str(e))

        simulated_time = None
        if self.spec.job_type == "RunTest":
            try:
                time, unit = plugin.get_simulated_time(self.spec, log_text=lines)
                simulated_time = JobTime(time, unit)
            except RuntimeError as e:
                log.debug("%s: %s", self.spec.full_name, str(e))

        return runtime, simulated_time
