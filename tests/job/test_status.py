# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test Job (scheduler) status modelling."""

from hamcrest import assert_that, equal_to

from dvsim.job.status import JobStatus


class TestJobStatus:
    """Test scheduler JobStatus models."""

    @staticmethod
    def test_unique_shorthands() -> None:
        """Test that all scheduler job statuses have unique shorthand representations."""
        shorthands = [status.shorthand for status in JobStatus]
        assert_that(len(set(shorthands)), equal_to(len(shorthands)))
