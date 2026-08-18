# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test git helpers."""

from pathlib import Path

import pytest
from git import Repo
from hamcrest import assert_that, calling, equal_to, raises

from dvsim.utils.git import (
    git_commit_hash,
    git_https_url_with_commit,
    git_is_dirty,
    git_origin_url,
    repo_root,
)

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
        # Value error if called outside a git repo
        assert_that(
            calling(git_commit_hash).with_args(tmp_path),
            raises(ValueError),
        )

        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")

        assert_that(
            git_commit_hash(tmp_path),
            equal_to(r.head.commit.hexsha),
        )

    @staticmethod
    def test_git_short_commit_hash(tmp_path: "Path") -> None:
        """Test that the expected shortened git commit sha is returned."""
        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")

        assert_that(
            git_commit_hash(tmp_path, short=True), equal_to(r.git.rev_parse(r.head, short=True))
        )

    @staticmethod
    def test_git_is_dirty(tmp_path: Path) -> None:
        """Test that git_is_dirty reflects the working tree state."""
        # Value error if called outside a git repo
        assert_that(
            calling(git_is_dirty).with_args(tmp_path),
            raises(ValueError),
        )

        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")

        # Clean tree
        assert_that(git_is_dirty(tmp_path), equal_to(False))

        # Modify a tracked file — now dirty
        file.write_text("changed")
        assert_that(git_is_dirty(tmp_path), equal_to(True))

    @staticmethod
    def test_git_origin_url(tmp_path: Path) -> None:
        """Test that the expected git remote origin url is returned."""
        # Value error if called outside a git repo
        assert_that(
            calling(git_origin_url).with_args(tmp_path),
            raises(ValueError),
        )

        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")

        # None if the repo has no 'origin' remote configured
        assert_that(git_origin_url(tmp_path), equal_to(None))

        # Still None if there are remotes but none named 'origin'
        r.create_remote("upstream", "git@github.com:lowRISC/other.git")
        assert_that(git_origin_url(tmp_path), equal_to(None))

        url = "git@github.com:lowRISC/test.git"
        r.create_remote("origin", url)

        assert_that(
            git_origin_url(tmp_path),
            equal_to(url),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            (
                "https://github.com/lowRISC/test.git",
                "https://github.com/lowRISC/test.git",
            ),
            ("git@github.com:lowRISC/test.git", "git@github.com:lowRISC/test.git"),
            # An ssh user is part of the address rather than a credential, so it stays. Dropping
            # it would leave a url that no longer reaches the remote.
            (
                "ssh://git@github.com/lowRISC/test.git",
                "ssh://git@github.com/lowRISC/test.git",
            ),
            (
                "git+ssh://git@github.com/lowRISC/test.git",
                "git+ssh://git@github.com/lowRISC/test.git",
            ),
            (
                "https://oauth2:ghs_secrettoken@github.com/lowRISC/test.git",
                "https://github.com/lowRISC/test.git",
            ),
            (
                "https://someuser@github.com/lowRISC/test.git",
                "https://github.com/lowRISC/test.git",
            ),
            # A password is a credential whatever the scheme carries it.
            (
                "ssh://user:secretpw@github.com/lowRISC/test.git",
                "ssh://github.com/lowRISC/test.git",
            ),
        ],
        ids=[
            "plain_https",
            "ssh_scp_form",
            "ssh_url_form",
            "git_ssh_scheme",
            "token",
            "user_only",
            "ssh_with_password",
        ],
    )
    def test_git_origin_url_strips_credentials(tmp_path: Path, url: str, expected: str) -> None:
        """A token in the remote url never reaches the caller, whatever the url's shape.

        The url is recorded in the run metadata and published in the reports, so a credential
        left in it outlives the run. Both ssh forms carry an '@' without being credentialed, and
        have to survive untouched or the recorded url stops addressing the remote.
        """
        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")
        r.create_remote("origin", url)

        assert_that(git_origin_url(tmp_path), equal_to(expected))

    @staticmethod
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("git@github.com:lowRISC/test.git", "https://github.com/lowRISC/test/tree/{commit}"),
            (
                "https://github.com/lowRISC/test.git",
                "https://github.com/lowRISC/test/tree/{commit}",
            ),
            (
                "https://oauth2:ghs_secrettoken@github.com/lowRISC/test.git",
                "https://github.com/lowRISC/test/tree/{commit}",
            ),
        ],
    )
    def test_git_https_url_with_commit(tmp_path: Path, url: str, expected: str) -> None:
        """Test that the expected url with commit is returned."""
        r = Repo.init(path=tmp_path)

        file = tmp_path / "a"
        file.write_text("file to commit")
        r.index.add([file])
        r.index.commit("initial commit")

        # Returns None when no 'origin' remote is configured.
        assert_that(git_https_url_with_commit(tmp_path), equal_to(None))

        r.create_remote("origin", url)

        commit = r.head.commit.hexsha
        assert_that(
            git_https_url_with_commit(tmp_path),
            equal_to(expected.format(commit=commit)),
        )
