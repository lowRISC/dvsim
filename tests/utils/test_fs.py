# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test file system utilities."""

from pathlib import Path

import pytest
from hamcrest import assert_that, calling, equal_to, raises

from dvsim.utils.fs import mk_path, mk_symlink, rm_path


def test_symlink_creation(tmp_path: Path) -> None:
    """Test that a dir path can be created."""
    src_path = tmp_path / "a"
    dest_path = tmp_path / "b"

    mk_symlink(path=dest_path, link=src_path)

    assert_that(src_path.is_symlink(), equal_to(True))

    # Despite the dest_path not yet existing the two paths should still
    # resolve to the same path
    assert_that(src_path.resolve(), equal_to(dest_path))

    # Make a temporary file in the destination directory
    dest_path.mkdir(parents=True)
    (dest_path / "temp").touch()

    # Check the file is now visible from the symlink
    assert_that((src_path / "temp").exists(), equal_to(True))

    # remove the created file via the symlink
    rm_path(src_path / "temp")

    # Check it's gone
    assert_that((src_path / "temp").exists(), equal_to(False))

    rm_path(src_path)

    # Check the symlink itself has been removed and not the destination dir
    assert_that(src_path.exists(), equal_to(False))
    assert_that(dest_path.exists(), equal_to(True))


def test_overwrite_file_with_symlink_raises(tmp_path: Path) -> None:
    """Test that existing files are not overwritten unless they are symlinks."""
    src_path = tmp_path / "a"
    dest_path = tmp_path / "b"

    src_path.touch()

    assert_that(
        calling(mk_symlink).with_args(path=dest_path, link=src_path),
        raises(TypeError),
    )


@pytest.mark.parametrize(
    ("test_path", "exp_glob"),
    [
        (
            Path("a"),
            [
                Path("a"),
            ],
        ),
        (
            Path("a") / "b",
            [
                Path("a"),
                Path("a") / "b",
            ],
        ),
        (
            Path("a") / "b" / "c",
            [
                Path("a"),
                Path("a") / "b",
                Path("a") / "b" / "c",
            ],
        ),
    ],
)
def test_path_creation(
    tmp_path: Path,
    test_path: Path,
    exp_glob: list[Path],
) -> None:
    """Test that a dir path can be created."""
    mk_path(tmp_path / test_path)

    assert_that(
        # Ignore the first element which is always Path(".")
        [p.relative_to(tmp_path) for p in tmp_path.glob("**")][1:],
        equal_to(exp_glob),
    )


@pytest.mark.parametrize(
    ("dir_paths", "file_paths", "remove_path", "exp_glob"),
    [
        # Remove a single level
        ([Path("a")], [], Path("a"), []),
        ([], [Path("a")], Path("a"), []),
        # Remove a path that doesn't exist
        ([], [], Path("a"), []),
        ([], [Path("b")], Path("a"), [Path("b")]),
        # Multiple levels
        (
            [Path("a") / "b", Path("a") / "c"],
            [],
            Path("a"),
            [],
        ),
        (
            [Path("a") / "b" / "c"],
            [],
            Path("a") / "b",
            [
                Path("a"),
            ],
        ),
        (
            [Path("a") / "b" / "c"],
            [Path("a") / "c"],
            Path("a") / "b",
            [
                Path("a"),
                Path("a") / "c",
            ],
        ),
    ],
)
def test_path_removal(
    tmp_path: Path,
    dir_paths: list[Path],
    file_paths: list[Path],
    remove_path: Path,
    exp_glob: list[Path],
) -> None:
    """Test that an existing path can be removed."""
    for d in dir_paths:
        mk_path(tmp_path / d)

    for f in file_paths:
        (tmp_path / f).write_text("")

    rm_path(tmp_path / remove_path)

    assert_that(
        # Ignore the first element which is always Path(".")
        [p.relative_to(tmp_path) for p in tmp_path.glob("**/*")],
        equal_to(exp_glob),
    )
