# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Git utility functions."""

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


def git_commit_hash(path: Path | None = None, *, short: bool = False) -> str:
    """Hash of the current git commit."""
    root = repo_root(path=path or Path.cwd())

    if root is None:
        log.error("no git repo found at %s", path)
        raise ValueError

    r = Repo(root)

    if short:
        return r.git.rev_parse(r.head, short=True)

    return r.head.commit.hexsha


def git_origin_url(path: Path | None = None) -> str:
    """Get the git remote origin url."""
    root = repo_root(path=path or Path.cwd())

    if root is None:
        log.error("no git repo found at %s", path)
        raise ValueError

    r = Repo(root)

    return r.remote().url


def git_https_url_with_commit(path: Path | None = None) -> str:
    """Get an https url that references the current commit.

    Args:
        path: the path to the git repo

    Returns:
        str containing the https url

    """
    url = git_origin_url(path=path)
    commit = git_commit_hash(path=path)

    url = url.removesuffix(".git")

    prefix = "git@github.com:"
    if url.startswith(prefix):
        url = "https://github.com/" + url.removeprefix(prefix)

    return f"{url}/tree/{commit}"
