# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test time-based utilities."""

import pytest
from hamcrest import assert_that, calling, equal_to, raises

from dvsim.utils.time import format_time_as_hms, format_time_metric


@pytest.mark.parametrize("seconds", [-0.001, -1, -500, -999999])
@pytest.mark.parametrize("decimals", [0, 2, 10])
def test_format_negative_times(seconds: float, decimals: int) -> None:
    """Test that the time formatting functions do not allow negative times to be provided."""
    assert_that(
        calling(format_time_as_hms).with_args(seconds, decimals=decimals),
        raises(ValueError, "negative"),
    )
    assert_that(
        calling(format_time_metric).with_args(
            seconds, hms_decimals=decimals, second_decimals=decimals
        ),
        raises(ValueError, "negative"),
    )


@pytest.mark.parametrize(
    ("seconds", "decimals", "omit_zero", "expected"),
    [
        (0, 0, True, "0s"),
        (0, 0, False, "0h 0m 0s"),
        (1.2345, 0, True, "1s"),
        (1.2345, 2, True, "1.23s"),
        (1.2345, 5, True, "1.23450s"),
        (9.8765, 2, True, "9.88s"),
        (1.2345, 2, False, "0h 0m 1.23s"),
        (60, 0, False, "0h 1m 0s"),
        (98.765, 1, True, "1m 38.8s"),
        (3600, 0, True, "1h 0m 0s"),
        (1234567.89, 2, True, "342h 56m 7.89s"),
    ],
)
def test_format_time(*, seconds: float, decimals: int, omit_zero: bool, expected: str) -> None:
    """Test that times can be correctly formatted in hour/minute/second format."""
    assert_that(
        format_time_as_hms(seconds, decimals=decimals, omit_zero=omit_zero), equal_to(expected)
    )


@pytest.mark.parametrize(
    ("seconds", "hms_decimals", "second_decimals", "omit_zero", "expected"),
    [
        (0, 0, 0, True, "0s (0s)"),
        (0, 0, 0, False, "0h 0m 0s (0s)"),
        (1.2345, 0, 0, True, "1s (1s)"),
        (1.2345, 2, 5, False, "0h 0m 1.23s (1.23450s)"),
        (60, 0, 0, False, "0h 1m 0s (60s)"),
        (98.765, 1, 5, True, "1m 38.8s (98.76500s)"),
        (3600, 0, 0, True, "1h 0m 0s (3,600s)"),
        (1234567.89, 1, 2, True, "342h 56m 7.9s (1,234,567.89s)"),
    ],
)
def test_format_time_metric(
    *, seconds: float, hms_decimals: int, second_decimals: int, omit_zero: bool, expected: str
) -> None:
    """Test that metric times can be correctly formatted."""
    assert_that(
        format_time_metric(
            seconds, hms_decimals=hms_decimals, second_decimals=second_decimals, omit_zero=omit_zero
        ),
        equal_to(expected),
    )
