# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Git utility functions."""

import logging as log
from pathlib import Path

from git import Repo

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


def git_commit_hash(path: Path | None = None, *, short: bool = False) -> str:
    """Hash of the current git commit."""
    root = repo_root(path=path or Path.cwd())

    if root is None:
        log.error("no git repo found at %s", root)
        raise ValueError

    r = Repo(root)

    if short:
        return r.git.rev_parse(r.head, short=True)

    return r.head.commit.hexsha
