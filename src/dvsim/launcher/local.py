# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Launcher implementation to run jobs as subprocesses on the local machine."""

import datetime
import os
import shlex
import subprocess
from typing import TYPE_CHECKING

from dvsim.launcher.base import ErrorMessage, Launcher, LauncherBusyError, LauncherError

if TYPE_CHECKING:
    from dvsim.job.data import JobSpec
    from dvsim.job.deploy import WorkspaceConfig


class LocalLauncher(Launcher):
    """Implementation of Launcher to launch jobs in the user's local workstation."""

    # Poll job's completion status every this many seconds
    poll_freq = 0.025

    def __init__(self, job_spec: "JobSpec") -> None:
        """Initialize common class members."""
        super().__init__(job_spec)

        # Popen object when launching the job.
        self._process = None
        self._log_file = None

    def _do_launch(self) -> None:
        # Update the shell's env vars with self.exports. Values in exports must
        # replace the values in the shell's env vars if the keys match.
        exports = os.environ.copy()
        exports.update(self.job_spec.exports)

        # Clear the magic MAKEFLAGS variable from exports if necessary. This
        # variable is used by recursive Make calls to pass variables from one
        # level to the next. Here, self.cmd is a call to Make but it's
        # logically a top-level invocation: we don't want to pollute the flow's
        # Makefile with Make variables from any wrapper that called dvsim.
        if "MAKEFLAGS" in exports:
            del exports["MAKEFLAGS"]

        self._dump_env_vars(exports)

        if not self.job_spec.interactive:
            log_path = self.job_spec.log_path
            timeout_mins = self.job_spec.timeout_mins

            self.timeout_secs = timeout_mins * 60 if timeout_mins else None

            try:
                self._log_file = log_path.open(
                    "w",
                    encoding="UTF-8",
                    errors="surrogateescape",
                )
                self._log_file.write(f"[Executing]:\n{self.job_spec.cmd}\n\n")
                self._log_file.flush()

                self._process = subprocess.Popen(
                    shlex.split(self.job_spec.cmd),
                    bufsize=4096,
                    universal_newlines=True,
                    stdout=self._log_file,
                    stderr=self._log_file,
                    env=exports,
                )

            except BlockingIOError as e:
                msg = f"Failed to launch job: {e}"
                raise LauncherBusyError(msg) from e

            except subprocess.SubprocessError as e:
                msg = f"IO Error: {e}\nSee {log_path}"
                raise LauncherError(msg) from e

            finally:
                self._close_job_log_file()
        else:
            # Interactive: Set RUN_INTERACTIVE to 1
            exports["RUN_INTERACTIVE"] = "1"

            # Interactive. stdin / stdout are transparent
            # no timeout and blocking op as user controls the flow
            self._process = subprocess.Popen(
                shlex.split(self.job_spec.cmd),
                stdin=None,
                stdout=None,
                stderr=subprocess.STDOUT,
                # string mode
                universal_newlines=True,
                env=exports,
            )

            # Wait until the process exit
            self._process.wait()

        self._link_odir("D")

    def poll(self) -> str | None:
        """Check status of the running process.

        This returns 'D', 'P', 'F', or 'K'. If 'D', the job is still running.
        If 'P', the job finished successfully. If 'F', the job finished with
        an error. If 'K' it was killed.

        This function must only be called after running self.dispatch_cmd() and
        must not be called again once it has returned 'P' or 'F'.
        """
        if self._process is None:
            return "E"

        elapsed_time = datetime.datetime.now() - self.start_time
        self.job_runtime_secs = elapsed_time.total_seconds()
        if self._process.poll() is None:
            if (
                self.timeout_secs
                and (self.job_runtime_secs > self.timeout_secs)
                and not (self.job_spec.gui)
            ):
                self._kill()
                timeout_mins = self.job_spec.timeout_mins
                timeout_message = f"Job timed out after {timeout_mins} minutes"
                self._post_finish(
                    "K",
                    ErrorMessage(
                        line_number=None,
                        message=timeout_message,
                        context=[timeout_message],
                    ),
                )
                return "K"

            return "D"

        self.exit_code = self._process.returncode
        status, err_msg = self._check_status()
        self._post_finish(status, err_msg)

        return self.status

    def _kill(self) -> None:
        """Kill the running process.

        Try to kill the running process. Send SIGTERM first, wait a bit,
        and then send SIGKILL if it didn't work.
        """
        if self._process is None:
            # process already dead or didn't start
            return

        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def kill(self) -> None:
        """Kill the running process.

        This must be called between dispatching and reaping the process (the
        same window as poll()).
        """
        self._kill()
        self._post_finish(
            "K",
            ErrorMessage(line_number=None, message="Job killed!", context=[]),
        )

    def _post_finish(self, status: str, err_msg: ErrorMessage | None) -> None:
        self._close_job_log_file()
        self._process = None
        super()._post_finish(status, err_msg)

    def _close_job_log_file(self) -> None:
        """Close the file descriptors associated with the process."""
        if self._log_file:
            self._log_file.close()

    @staticmethod
    def prepare_workspace(cfg: "WorkspaceConfig") -> None:
        """Prepare the workspace based on the chosen launcher's needs.

        This is done once for the entire duration for the flow run.

        Args:
            cfg: workspace configuration

        """

    @staticmethod
    def prepare_workspace_for_cfg(cfg: "WorkspaceConfig") -> None:
        """Prepare the workspace for a cfg.

        This is invoked once for each cfg.

        Args:
            cfg: workspace configuration

        """
