# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Launcher abstract base class."""

import datetime
import os
import re
import sys
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from dvsim.job.time import JobTime
from dvsim.logging import log
from dvsim.tool.utils import get_sim_tool_plugin
from dvsim.utils import clean_odirs, mk_symlink, rm_path

if TYPE_CHECKING:
    from dvsim.job.data import JobSpec, WorkspaceConfig


class LauncherError(Exception):
    """Error occurred during job launching."""


class LauncherBusyError(Exception):
    """Launcher is busy and the job was not able to be launched."""


class ErrorMessage(BaseModel):
    """Contains error-related information.

    This support classification of failures into buckets. The message field
    is used to generate the bucket, and context contains a list of lines in
    the failing log that can be useful for quick diagnostics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    line_number: int | None = None
    message: str
    context: Sequence[str]


class Launcher(ABC):
    """Abstraction for launching and maintaining a job.

    An abstract class that provides methods to prepare a job's environment,
    launch the job, poll for its completion and finally do some cleanup
    activities. This class is not meant to be instantiated directly. Each
    launcher object holds an instance of the deploy object.
    """

    # Type of launcher used as string.
    variant: str | None = None

    # Max jobs running at one time
    max_parallel = sys.maxsize

    # Max jobs polled at one time
    max_poll = 10000

    # Poll job's completion status every this many seconds
    poll_freq = 1

    # Points to the python virtual env area.
    pyvenv: Path | None = None

    # If a history of previous invocations is to be maintained, then keep no
    # more than this many directories.
    max_odirs = 5

    # Flag indicating the workspace preparation steps are complete.
    workspace_prepared = False
    workspace_prepared_for_cfg = set()

    # Jobs that are not run when one of their dependent jobs fail are
    # considered killed. All non-passing jobs are required to have an
    # an associated fail_msg attribute (an object of class ErrorMessage)
    # reflecting the appropriate message. This class attribute thus serves
    # as a catch-all for all those jobs that are not even run. If a job
    # instance runs and fails, the fail_msg attribute is overridden by
    # the instance with the correct message in _post_finish().
    fail_msg = ErrorMessage(
        line_number=None,
        message="Job killed most likely because its dependent job failed.",
        context=[],
    )

    def __init__(self, job_spec: "JobSpec") -> None:
        """Initialise launcher.

        Args:
            job_spec: job specification for the job to be launched.

        """
        workspace_cfg = job_spec.workspace_cfg

        # One-time preparation of the workspace.
        if not Launcher.workspace_prepared:
            self.prepare_workspace(workspace_cfg)
            Launcher.workspace_prepared = True

        # One-time preparation of the workspace, specific to the cfg.
        project = workspace_cfg.project
        if project not in Launcher.workspace_prepared_for_cfg:
            self.prepare_workspace_for_cfg(workspace_cfg)
            Launcher.workspace_prepared_for_cfg.add(project)

        self.job_spec = job_spec

        # Status of the job. This is primarily determined by the
        # _check_status() method, but eventually updated by the _post_finish()
        # method, in case any of the cleanup tasks fails. This value is finally
        # returned to the Scheduler by the poll() method.
        self.status = None

        # Return status of the process running the job.
        self.exit_code = None

        # Flag to indicate whether to 'overwrite' if odir already exists,
        # or to backup the existing one and create a new one.
        # For builds, we want to overwrite existing to leverage the tools'
        # incremental / partition compile features. For runs, we may want to
        # create a new one.
        self.renew_odir = False

        # The actual job runtime computed by dvsim, in seconds.
        self.job_runtime_secs = 0

        # Job's wall clock time (a.k.a CPU time, or runtime).
        # Field copied over from Deploy
        # TODO: factor this out
        self.job_runtime = JobTime()
        self.simulated_time = JobTime()

    def __str__(self) -> str:
        """Get a string representation."""
        return self.job_spec.full_name + ":launcher"

    @staticmethod
    def set_pyvenv(project: str) -> None:
        """Activate a python virtualenv if available.

        The env variable <PROJECT>_PYTHON_VENV if set, points to the path
        containing the python virtualenv created specifically for this
        project. We can activate it if needed, before launching jobs using
        external compute machines.

        This is not applicable when running jobs locally on the user's machine.
        """
        if Launcher.pyvenv is not None:
            return

        # If project-specific python virtualenv path is set, then activate it
        # before running downstream tools. This is more relevant when not
        # launching locally, but on external machines in a compute farm, which
        # may not have access to the default python installation area on the
        # host machine.
        #
        # The code below allows each launcher variant to set its own virtualenv
        # because the loading / activating mechanism could be different between
        # them.
        common_venv = f"{project.upper()}_PYVENV"
        variant = Launcher.variant.upper()

        venv_path = os.environ.get(f"{common_venv}_{variant}")

        if not venv_path:
            venv_path = os.environ.get(common_venv)

        if venv_path:
            Launcher.pyvenv = Path(venv_path)

    @staticmethod
    @abstractmethod
    def prepare_workspace(cfg: "WorkspaceConfig") -> None:
        """Prepare the workspace based on the chosen launcher's needs.

        This is done once for the entire duration for the flow run.

        Args:
            cfg: workspace configuration

        """

    @staticmethod
    @abstractmethod
    def prepare_workspace_for_cfg(cfg: "WorkspaceConfig") -> None:
        """Prepare the workspace for a cfg.

        This is invoked once for each cfg.
        'cfg' is the flow configuration object.

        Args:
            cfg: workspace configuration

        """

    def _make_odir(self) -> None:
        """Create the output directory."""
        # If renew_odir flag is True - then move it.
        if self.renew_odir:
            clean_odirs(odir=self.job_spec.odir, max_odirs=self.max_odirs)

        Path(self.job_spec.odir).mkdir(exist_ok=True, parents=True)

    def _link_odir(self, status: str) -> None:
        """Soft-links the job's directory based on job's status.

        The dispatched, passed and failed directories in the scratch area
        provide a quick way to get to the job that was executed.
        """
        dest = Path(self.job_spec.links[status], self.job_spec.qual_name)
        mk_symlink(path=self.job_spec.odir, link=dest)

        # Delete the symlink from dispatched directory if it exists.
        if status != "D":
            old = Path(self.job_spec.links["D"], self.job_spec.qual_name)
            rm_path(old)

    def _dump_env_vars(self, exports: Mapping[str, str]) -> None:
        """Write env vars to a file for ease of debug.

        Each extended class computes the list of exports and invokes this
        method right before launching the job.
        """
        with (self.job_spec.odir / "env_vars").open(
            "w",
            encoding="UTF-8",
            errors="surrogateescape",
        ) as f:
            f.writelines(f"{var}={exports[var]}\n" for var in sorted(exports.keys()))

    def _pre_launch(self) -> None:
        """Do pre-launch activities.

        Examples include such as preparing the job's environment, clearing
        old runs, creating the output directory, dumping all env variables
        etc. This method is already invoked by launch() as the first step.
        """
        self.job_spec.pre_launch(self)
        self._make_odir()
        self.start_time = datetime.datetime.now()

    @abstractmethod
    def _do_launch(self) -> None:
        """Launch the job."""

    def launch(self) -> None:
        """Launch the job."""
        self._pre_launch()
        self._do_launch()

    @abstractmethod
    def poll(self) -> str | None:
        """Poll the launched job for completion.

        Invokes _check_status() and _post_finish() when the job completes.

        Returns:
            status of the job or None

        """

    @abstractmethod
    def kill(self) -> None:
        """Terminate the job."""

    def _check_status(self) -> tuple[str, ErrorMessage | None]:
        """Determine the outcome of the job (P/F if it ran to completion).

        Returns:
            (status, err_msg) extracted from the log, where the status is
            "P" if the it passed, "F" otherwise. This is invoked by poll() just
            after the job finishes. err_msg is an instance of the named tuple
            ErrorMessage.

        """

        def _find_patterns(patterns: Sequence[str], line: str) -> Sequence[str] | None:
            """Get all patterns that match the given line.

            Helper function that returns the pattern if any of the given
            patterns is found, else None.

            Args:
                patterns: sequence of regex patterns to check
                line: string to check matches against

            Returns:
                All matching patterns or None if there are no matches.

            """
            if not patterns:
                return None

            for pattern in patterns:
                match = re.search(rf"{pattern}", line)
                if match:
                    return pattern
            return None

        if self.job_spec.dry_run:
            return "P", None

        # Only one fail pattern needs to be seen.
        chk_failed = bool(self.job_spec.fail_patterns)

        # All pass patterns need to be seen, so we replicate the list and remove
        # patterns as we encounter them.
        pass_patterns = list(self.job_spec.pass_patterns).copy()
        chk_passed = bool(pass_patterns) and (self.exit_code == 0)

        try:
            with self.job_spec.log_path.open(
                encoding="UTF-8",
                errors="surrogateescape",
            ) as f:
                lines = f.readlines()
        except OSError as e:
            return "F", ErrorMessage(
                line_number=None,
                message=f"Error opening file {self.job_spec.log_path}:\n{e}",
                context=[],
            )

        # Since the log file is already opened and read to assess the job's
        # status, use this opportunity to also extract other pieces of
        # information.

        # Extracts the job's runtime (i.e. the wall clock time)
        # as reported by the tool. The tool reported runtime is the most accurate
        # since it is devoid of the delays incurred due to infrastructure and
        # setup overhead.

        plugin = get_sim_tool_plugin(tool=self.job_spec.tool)

        try:
            time, unit = plugin.get_job_runtime(log_text=lines)
            self.job_runtime.set(time, unit)

        except RuntimeError as e:
            log.warning(
                f"{self.job_spec.full_name}: {e} Using dvsim-maintained job_runtime instead."
            )
            self.job_runtime.set(self.job_runtime_secs, "s")

        if self.job_spec.job_type == "RunTest":
            try:
                time, unit = plugin.get_simulated_time(log_text=lines)
                self.simulated_time.set(time, unit)

            except RuntimeError as e:
                log.debug(f"{self.job_spec.full_name}: {e}")

        if chk_failed or chk_passed:
            for cnt, line in enumerate(lines):
                if chk_failed and _find_patterns(self.job_spec.fail_patterns, line):
                    # If failed, then nothing else to do. Just return.
                    # Provide some extra lines for context.
                    end = cnt + 5
                    return "F", ErrorMessage(
                        line_number=cnt + 1,
                        message=line.strip(),
                        context=lines[cnt:end],
                    )

                if chk_passed:
                    pattern = _find_patterns(pass_patterns, line)
                    if pattern:
                        pass_patterns.remove(pattern)
                        chk_passed = bool(pass_patterns)

        # If no fail patterns were seen, but the job returned with non-zero
        # exit code for whatever reason, then show the last 10 lines of the log
        # as the failure message, which might help with the debug.
        if self.exit_code != 0:
            return "F", ErrorMessage(
                line_number=None,
                message="Job returned non-zero exit code",
                context=lines[-10:],
            )
        if chk_passed:
            return "F", ErrorMessage(
                line_number=None,
                message=f"Some pass patterns missing: {pass_patterns}",
                context=lines[-10:],
            )
        return "P", None

    def _post_finish(self, status: str, err_msg: ErrorMessage) -> None:
        """Do post-completion activities, such as preparing the results.

        Must be invoked by poll(), after the job outcome is determined.

        Args:
            status: status of the job, either 'P', 'F' or 'K'.
            err_msg: an instance of the named tuple ErrorMessage.

        """
        assert status in ["P", "F", "K"]
        self._link_odir(status)
        log.debug("Item %s has completed execution: %s", self, status)

        try:
            # Run the target-specific cleanup tasks regardless of the job's
            # outcome.
            self.job_spec.post_finish(status)

        except Exception as e:
            # If the job had already failed, then don't do anything. If it's
            # cleanup task failed, then mark the job as failed.
            if status == "P":
                status = "F"
                err_msg = ErrorMessage(
                    line_number=None,
                    message=f"{e}",
                    context=[f"{e}"],
                )

        self.status = status
        if self.status != "P":
            assert err_msg
            assert isinstance(err_msg, ErrorMessage)
            self.fail_msg = err_msg
            log.verbose(err_msg.message)
