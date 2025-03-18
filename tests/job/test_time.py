# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test job runtime time helpers."""

import pytest
from hamcrest import assert_that, equal_to

from dvsim.job.time import JobTime

__all__ = ("TestJobTime",)


class TestJobTime:
    """Test JobTime."""

    @staticmethod
    @pytest.mark.parametrize(
        ("time", "unit", "exp_time", "exp_unit"),
        [
            # Automatic normalisation to higher units to avoid large numbers
            # fs
            (10, "fs", 10, "fs"),
            (1e3, "fs", 1, "ps"),
            (1e6, "fs", 1, "ns"),
            (1e9, "fs", 1, "us"),
            (1e12, "fs", 1, "ms"),
            (1e15, "fs", 1, "s"),
            (60 * 1e15, "fs", 1, "m"),
            (60 * 60 * 1e15, "fs", 1, "h"),
            # ps
            (10, "ps", 10, "ps"),
            (1e3, "ps", 1, "ns"),
            (1e6, "ps", 1, "us"),
            (1e9, "ps", 1, "ms"),
            (1e12, "ps", 1, "s"),
            (60 * 1e12, "ps", 1, "m"),
            (60 * 60 * 1e12, "ps", 1, "h"),
            # ns
            (10, "ns", 10, "ns"),
            (1e3, "ns", 1, "us"),
            (1e6, "ns", 1, "ms"),
            (1e9, "ns", 1, "s"),
            (60 * 1e9, "ns", 1, "m"),
            (60 * 60 * 1e9, "ns", 1, "h"),
            # us
            (10, "us", 10, "us"),
            (1e3, "us", 1, "ms"),
            (1e6, "us", 1, "s"),
            (60 * 1e6, "us", 1, "m"),
            (60 * 60 * 1e6, "us", 1, "h"),
            # ms
            (10, "ms", 10, "ms"),
            (1e3, "ms", 1, "s"),
            (60 * 1e3, "ms", 1, "m"),
            (60 * 60 * 1e3, "ms", 1, "h"),
            # s
            (0, "s", 0, "s"),
            (10, "s", 10, "s"),
            (2 * 60, "s", 2, "m"),
            (60 * 60, "s", 1, "h"),
            (5400, "s", 1.5, "h"),
            (7200, "s", 2, "h"),
            # m
            (10, "m", 10, "m"),
            (120, "m", 2, "h"),
            (3600, "m", 60, "h"),
            (5400, "m", 90, "h"),
            (7200, "m", 120, "h"),
            # Don't normalise to lower units?
            (0.5, "fs", 0.5, "fs"),
            (0.5, "ps", 0.5, "ps"),
            (0.5, "ns", 0.5, "ns"),
            (0.5, "us", 0.5, "us"),
            (0.5, "ms", 0.5, "ms"),
            (0.5, "m", 0.5, "m"),
            (0.001, "m", 0.001, "m"),
            (0.001, "h", 0.001, "h"),
        ],
    )
    def test_initialise(
        time: float,
        unit: str,
        exp_time: float,
        exp_unit: str,
    ) -> None:
        """Test that JobTime can be inititialised."""
        assert_that(
            JobTime(time=time, unit=unit).get(),
            equal_to((exp_time, exp_unit)),
        )

        # Same test using set
        jt = JobTime()
        jt.set(time=time, unit=unit)
        assert_that(
            jt.get(),
            equal_to((exp_time, exp_unit)),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("time", "unit", "time2", "unit2", "exp"),
        [
            (1, "s", 1, "ms", True),
            (1, "fs", 1, "ms", False),
            (61, "s", 1, "m", True),
            (0, "s", 0, "s", False),
            (0, "m", 0, "s", False),
        ],
    )
    def test_greater_than(
        *,
        time: float,
        unit: str,
        time2: float,
        unit2: str,
        exp: bool,
    ) -> None:
        """Test that JobTime can be inititialised."""
        assert_that(
            JobTime(time=time, unit=unit, normalize=False)
            > JobTime(time=time2, unit=unit2, normalize=False),
            equal_to(exp),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("time", "unit", "time2", "unit2"),
        [
            (1, "s", 1, "s"),
            (1, "m", 1, "m"),
            (60, "s", 1, "m"),
        ],
    )
    def test_equal_to(
        *,
        time: float,
        unit: str,
        time2: float,
        unit2: str,
    ) -> None:
        """Test that JobTime can be inititialised."""
        assert_that(
            JobTime(time=time, unit=unit, normalize=False),
            equal_to(JobTime(time=time2, unit=unit2, normalize=False)),
        )

    @staticmethod
    def test_with_unit() -> None:
        """Test that with_unit returns a JobTime with the given unit."""
        # First data set
        h = JobTime(6, "h", normalize=False)
        m = JobTime(360, "m", normalize=False)
        s = JobTime(21600, "s", normalize=False)
        ms = JobTime(21600000, "ms", normalize=False)
        for src in [h, m, s, ms]:
            for unit, dst in [("h", h), ("m", m), ("s", s), ("ms", ms)]:
                assert_that(src.with_unit(unit), equal_to(dst))

        # Second data set
        fs = JobTime(123456000000, "fs", normalize=False)
        ps = JobTime(123456000, "ps", normalize=False)
        ns = JobTime(123456, "ns", normalize=False)
        us = JobTime(123.456, "us", normalize=False)
        ms = JobTime(0.123456, "ms", normalize=False)
        for src in [fs, ps, ns, us, ms]:
            for unit, dst in [("fs", fs), ("ps", ps), ("ns", ns), ("us", us), ("ms", ms)]:
                assert_that(src.with_unit(unit), equal_to(dst))
