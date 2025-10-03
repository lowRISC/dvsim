# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Git utinity functions."""

from pathlib import Path

from git import Repo

from dvsim.logging import log

__all__ = ("repo_root",)


def repo_root(path: Path) -> Path | None:
    """Given a sub dir in a git repo provide the root path.

    Where the provided path is not part of a repo then None is returned.
    """
    if (path / ".git").exists():
        return path

    for p in path.parents:
        if (p / ".git").exists():
            return p

    return None


def git_commit_hash(path: Path | None = None) -> str:
    """Hash of the current git commit."""
    root = repo_root(path=path if path else Path.cwd())

    if root is None:
        log.error("no git repo found at %s", root)
        raise ValueError

    r = Repo(root)

    return r.head.commit.hexsha
