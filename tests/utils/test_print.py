# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test printing / CLI utilities."""

import pytest
from hamcrest import assert_that, equal_to

from dvsim.utils.print import ordinal_suffix


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "th"),
        (1, "st"),
        (2, "nd"),
        (3, "rd"),
        (4, "th"),
        (9, "th"),
        (10, "th"),
        (11, "th"),
        (12, "th"),
        (13, "th"),
        (18, "th"),
        (100, "th"),
        (111, "st"),
        (222, "nd"),
        (333, "rd"),
        (444, "th"),
        (12345678, "th"),
    ],
)
def test_ordinal_suffix(n: int, expected: str) -> None:
    """Test that the correct ordinal suffix is calculated by the utility."""
    assert_that(ordinal_suffix(n), equal_to(expected))
