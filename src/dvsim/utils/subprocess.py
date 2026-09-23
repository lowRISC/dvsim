# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utilities for running external tools."""

import shlex
import subprocess
import sys
import time

from dvsim.logging import log

# An {eval_cmd} is a shell snippet from a flow config, so its output on failure is usually a line
# or two. It does not have to be: a snippet that shells out to find or to a script can produce a
# great deal before it fails, and flooding the terminal with all of it helps nobody. Keep the tail,
# where the error almost always is.
_MAX_FAILURE_LINES = 20


def _log_failure_output(output: str) -> None:
    """Log a failing command's output, keeping only the tail when it is long."""
    lines = output.strip().splitlines()
    if not lines:
        return

    if len(lines) > _MAX_FAILURE_LINES:
        log.error(
            "Last %d of %d output lines:",
            _MAX_FAILURE_LINES,
            len(lines),
        )
        lines = lines[-_MAX_FAILURE_LINES:]

    log.error("%s", "\n".join(lines))


def run_cmd(cmd: str) -> str:
    """Run a command and get the result.

    Exit with error if the command did not succeed. This is a simpler version
    of the run_cmd_with_timeout function below.
    """
    (status, output) = subprocess.getstatusoutput(cmd)
    if status:
        # getstatusoutput folds stderr into output, so this is the only place the command's
        # diagnostic exists. Dropping it leaves the user with a bare exit status and no clue,
        # which is what a flow config that guards a missing tool with ${VAR:?message} hits.
        log.error("Command failed with status %d: %s", status, cmd)
        _log_failure_output(output)
        sys.exit(status)

    return output


def run_cmd_with_timeout(
    cmd: str,
    *,
    timeout: float | None = None,
    exit_on_failure: bool = True,
) -> tuple[str, int]:
    """Run a command with a specified timeout.

    If the command does not finish before the timeout, then it returns -1. Else
    it returns the command output. If the command fails, it throws an exception
    and returns the stderr.
    """
    args = shlex.split(cmd)
    p = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # If timeout is set, poll for the process to finish until timeout
    result = ""
    status = -1
    if timeout:
        start = time.time()
        while time.time() - start < timeout:
            if p.poll():
                break

            time.sleep(0.01)
    else:
        p.wait()

    # Capture output and status if cmd exited, else kill it
    if p.poll():
        result = p.communicate()[0]
        status = p.returncode

    else:
        log.error('cmd "%s" timed out!', cmd)
        p.kill()

    if status != 0:
        log.error('cmd "%s" exited with status %d', cmd, status)
        if exit_on_failure:
            sys.exit(status)

    return (result, status)
