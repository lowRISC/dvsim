# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""SgeLauncher Class."""

import os
import shlex
import subprocess
from pathlib import Path
from subprocess import PIPE, Popen
from typing import TYPE_CHECKING

from dvsim.launcher.base import ErrorMessage, Launcher, LauncherError
from dvsim.launcher.sge.engine import *  # noqa: F403

if TYPE_CHECKING:
    from dvsim.job.deploy import WorkspaceConfig

global job_name

pid = os.getpid()


class SgeLauncher(Launcher):
    """Implementation of Launcher to launch jobs in the user's local workstation."""

    def __init__(self, deploy) -> None:
        """Initialize common class members."""
        super().__init__(deploy)

        # Popen object when launching the job.
        self.process = None

    def _do_launch(self) -> None:
        global job_name
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

        try:
            f = self.job_spec.log_path.open("w", encoding="UTF-8", errors="surrogateescape")
            f.write(f"[Executing]:\n{self.job_spec.cmd}\n\n")
            f.flush()

            # ---------- prepare SGE job struct -----
            sge_job = SGE.QSubOptions()  # noqa: F405
            sge_job.args.N = "VCS_RUN_" + str(pid)  # Name of Grid Engine job
            if "build.log" in self.job_spec.log_path:
                sge_job.args.N = "VCS_BUILD_" + str(pid)  # Name of Grid Engine job

            job_name = sge_job.args.N
            sge_job.args.t = "0"  # Define an array job with 20 subjobs
            sge_job.args.slot = "1"  # Define num of slot
            sge_job.args.sync = "y"  # wait for job to complete before exiting
            sge_job.args.q = "vcs_q"  # Define the sge queue name
            sge_job.args.p = "0"  # Set priority to 0
            sge_job.args.ll = "mf=20G"  # memory req,request the given resources

            # pecifies a range of priorities from -1023 to 1024.
            # The higher the number, the higher the priority.
            # The default priority for jobs is zero
            sge_job.args.command = '"' + self.job_spec.cmd + '"'
            sge_job.args.b = "y"  # This is a binary file
            sge_job.args.o = f"{self.job_spec.log_path}.sge"
            cmd = str(sge_job.execute(mode="echo"))

            self.process = subprocess.Popen(
                shlex.split(cmd),
                bufsize=4096,
                universal_newlines=True,
                stdout=f,
                stderr=f,
                env=exports,
            )
            f.close()

        except subprocess.SubprocessError as e:
            msg = f"IO Error: {e}\nSee {self.job_spec.log_path}"
            raise LauncherError(msg)

        finally:
            self._close_process()

        self._link_odir("D")
        f.close()

    def poll(self) -> str:
        """Check status of the running process.

        This returns 'D', 'P' or 'F'. If 'D', the job is still running. If 'P',
        the job finished successfully. If 'F', the job finished with an error.

        This function must only be called after running self.dispatch_cmd() and
        must not be called again once it has returned 'P' or 'F'.
        """
        assert self.process is not None
        if self.process.poll() is None:
            return "D"
        # -------------------------------------
        # copy SGE job results to log file
        sge_log_path = Path(f"{self.job_spec.log_path}.sge")
        if sge_log_path.exists():
            file1 = sge_log_path.open(errors="replace")
            lines = file1.readlines()
            file1.close()
            f = self.job_spec.log_path.open("a", encoding="UTF-8", errors="surrogateescape")
            f.writelines(lines)
            f.flush()
            sge_log_path.unlink()
            f.close()
        # -------------------------------------

        self.exit_code = self.process.returncode
        status, err_msg = self._check_status()
        self._post_finish(status, err_msg)
        return status

    def kill(self) -> None:
        global job_name
        """Kill the running process.

        This must be called between dispatching and reaping the process (the
        same window as poll()).

        """
        assert self.process is not None

        # Try to kill the running process. Send SIGTERM first, wait a bit,
        # and then send SIGKILL if it didn't work.
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            # ----------------------------
            # qdel -f kill sge job_name
            cmd = "qstatus -a | grep " + job_name
            with Popen(cmd, stdout=PIPE, stderr=None, shell=True) as process:  # noqa: S602
                output = process.communicate()[0].decode("utf-8")
                output = output.rstrip("\n")
                if output != "":
                    output_l = output.split()
                    cmd = "qdel " + output_l[0]
                    with Popen(cmd, stdout=PIPE, stderr=None, shell=True) as process:  # noqa: S602
                        output = process.communicate()[0].decode("utf-8")
                        output = output.rstrip("\n")
            # ----------------------------
        self._post_finish("K", ErrorMessage(line_number=None, message="Job killed!", context=[]))

    def _post_finish(self, status, err_msg) -> None:
        super()._post_finish(status, err_msg)
        self._close_process()
        self.process = None

    def _close_process(self) -> None:
        """Close the file descriptors associated with the process."""
        assert self.process
        if self.process.stdout:
            self.process.stdout.close()

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
