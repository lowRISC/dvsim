# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Fixtures shared by all the tests."""

import logging
import os
import subprocess
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def _git_repo_vars() -> list[str]:
    """Variables that point git at a repository other than the one it finds from the cwd.

    Git lists the variables that are local to a repository, so the list matches the git
    that the tests run. GIT_NAMESPACE isn't in it, but it changes which refs git sees.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        capture_output=True,
        check=True,
        text=True,
    )
    return [*result.stdout.split(), "GIT_NAMESPACE"]


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, _git_repo_vars: list[str]) -> None:
    """Keep the tests' git commands in the repositories that the tests make.

    Git hooks and `git rebase --exec` set GIT_DIR and friends, which would point the tests'
    git commands at the repository that the tests are run from. The user's and the system's
    git config (commit signing, hooks, templates) are left out too, and commits get a fixed
    author.
    """
    for var in _git_repo_vars:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "dvsim test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "dvsim-test@example.com")


@pytest.fixture
def dvsim_log(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture dvsim's own logger, which deliberately does not propagate."""
    logger = logging.getLogger("dvsim")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="dvsim")
    yield caplog
    logger.removeHandler(caplog.handler)
