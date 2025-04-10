# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utilities for running external tools."""

import shlex
import subprocess
import sys
import time

from dvsim.logging import log


def run_cmd(cmd: str) -> str:
    """Run a command and get the result.

    Exit with error if the command did not succeed. This is a simpler version
    of the run_cmd_with_timeout function below.
    """
    (status, output) = subprocess.getstatusoutput(cmd)
    if status:
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
