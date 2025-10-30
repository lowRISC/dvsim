# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import os
import pathlib
import shlex
import shutil
import subprocess
from typing import TYPE_CHECKING

from dvsim.launcher.base import ErrorMessage, Launcher, LauncherError
from dvsim.logging import log

if TYPE_CHECKING:
    from dvsim.job.deploy import WorkspaceConfig

SLURM_QUEUE = os.environ.get("SLURM_QUEUE", "hw-m")
SLURM_MEM = os.environ.get("SLURM_MEM", "16G")
SLURM_MINCPUS = os.environ.get("SLURM_MINCPUS", "8")
SLURM_TIMEOUT = os.environ.get("SLURM_TIMEOUT", "240")
SLURM_CPUS_PER_TASK = os.environ.get("SLURM_CPUS_PER_TASK", "8")
SLURM_SETUP_CMD = os.environ.get("SLURM_SLURM_SETUP_CMD", "")


class SlurmLauncher(Launcher):
    # Misc common SlurmLauncher settings.
    max_odirs = 5

    def __init__(self, deploy) -> None:
        """Initialize common class members."""
        super().__init__(deploy)

        # Popen object when launching the job.
        self.process = None
        self.slurm_log_file = f"{self.job_spec.log_path}.slurm"

    def _do_launch(self) -> None:
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

        # Add a command delimiter if necessary
        slurm_setup_cmd = SLURM_SETUP_CMD
        if slurm_setup_cmd and not slurm_setup_cmd.endswith(";"):
            slurm_setup_cmd += ";"

        # Encapsulate the run command with the slurm invocation
        slurm_cmd = (
            f"srun -p {SLURM_QUEUE} --mem={SLURM_MEM} --mincpus={SLURM_MINCPUS} "
            f"--time={SLURM_TIMEOUT} --cpus-per-task={SLURM_CPUS_PER_TASK} "
            f'bash -c "{slurm_setup_cmd} {self.job_spec.cmd}"'
        )

        try:
            with pathlib.Path(self.slurm_log_file).open("w") as out_file:
                out_file.write(f"[Executing]:\n{self.job_spec.cmd}\n\n")
                out_file.flush()

                log.info(f"Executing slurm command: {slurm_cmd}")
                self.process = subprocess.Popen(
                    shlex.split(slurm_cmd),
                    bufsize=4096,
                    universal_newlines=True,
                    stdout=out_file,
                    stderr=out_file,
                    env=exports,
                )
        except OSError as e:
            msg = f"File Error: {e}\nError while handling {self.slurm_log_file}"
            raise LauncherError(msg)
        except subprocess.SubprocessError as e:
            msg = f"IO Error: {e}\nSee {self.job_spec.log_path}"
            raise LauncherError(msg)
        finally:
            self._close_process()

        self._link_odir("D")

    def poll(self):
        """Check status of the running process.

        This returns 'D', 'P' or 'F'. If 'D', the job is still running. If 'P',
        the job finished successfully. If 'F', the job finished with an error.

        This function must only be called after running self.dispatch_cmd() and
        must not be called again once it has returned 'P' or 'F'.
        """
        assert self.process is not None
        if self.process.poll() is None:
            return "D"

        # Copy slurm job results to log file
        if pathlib.Path(self.slurm_log_file).exists():
            try:
                with pathlib.Path(self.slurm_log_file).open() as slurm_file:
                    try:
                        with self.job_spec.log_path.open("a") as out_file:
                            shutil.copyfileobj(slurm_file, out_file)
                    except OSError as e:
                        msg = f"File Error: {e} when handling {self.job_spec.log_path}"
                        raise LauncherError(
                            msg,
                        )
                # Remove the temporary file from the slurm process
                pathlib.Path(self.slurm_log_file).unlink()
            except OSError as e:
                msg = f"File Error: {e} when handling {self.slurm_log_file}"
                raise LauncherError(msg)

        self.exit_code = self.process.returncode
        status, err_msg = self._check_status()
        self._post_finish(status, err_msg)
        return status

    def kill(self) -> None:
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
