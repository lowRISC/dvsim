# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test rclone helper functions."""

from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to

from dvsim.utils.rclone import rclone_list_dirs


@pytest.mark.parametrize(
    ("dirs", "expected", "env"),
    [
        (("a", "b", "c"), {"a", "b", "c"}, {}),
        (
            (
                "a",
                "a/b",
            ),
            {"a"},
            {},
        ),
        (("a", "b", "c"), {"b", "c"}, {"RCLONE_EXCLUDE": "a/"}),
    ],
)
def test_rclone_list_dirs(
    dirs: Iterable[str],
    expected: set[str],
    tmp_path: Path,
    env: Mapping[str, str],
) -> None:
    """Assert that dirs listed are as expected."""
    # Create directories to list
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    assert_that(
        set(rclone_list_dirs(path=tmp_path, extra_env=env)),
        equal_to(expected),
    )
