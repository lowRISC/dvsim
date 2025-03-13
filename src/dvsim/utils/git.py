# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Git utinity functions."""

from dvsim.utils.subprocess import run_cmd

__all__ = ("git_commit_hash",)


def git_commit_hash() -> str:
    """Hash of the current git commit."""
    return run_cmd("git rev-parse HEAD")
