# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test git helpers."""

from pathlib import Path

from git import Repo
from hamcrest import assert_that, equal_to

from dvsim.utils.git import git_commit_hash, repo_root

__all__ = ()


class TestGit:
    """Test git helpers."""

    @staticmethod
    def test_repo_root(tmp_path: Path) -> None:
        """Test git repo root can be found."""
        repo_root_path = tmp_path / "repo"
        repo_root_path.mkdir()

        Repo.init(path=repo_root_path)

        # from the actual repo root
        assert_that(repo_root(path=repo_root_path), equal_to(repo_root_path))

        # from the repo sub dir
        sub_dir_path = repo_root_path / "a"
        sub_dir_path.mkdir()
        assert_that(repo_root(path=sub_dir_path), equal_to(repo_root_path))

        # from outside the repo
        assert_that(repo_root(path=tmp_path), equal_to(None))

    @staticmethod
    def test_git_commit_hash(tmp_path: Path) -> None:
        """Test that the expected git commit sha is returned."""
        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")

        assert_that(
            git_commit_hash(tmp_path),
            equal_to(r.head.commit.hexsha),
        )
