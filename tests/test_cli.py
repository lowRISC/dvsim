# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim cli."""

from hamcrest import assert_that, calling, raises

from dvsim.cli import main


def test_cli() -> None:
    """Test that the CLI can be called without args.

    This doesn't test anything specific, only that the cli module can be
    imported without errors and main function executes without errors. The
    expectation is that a usage message is presented.
    """
    assert_that(calling(main).with_args(), raises(SystemExit))
