# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test utilities for running external tools."""

import logging

import pytest
from hamcrest import assert_that, contains_string, equal_to, is_not

from dvsim.utils.subprocess import run_cmd

__all__ = ("TestRunCmd",)


@pytest.fixture
def dvsim_log(caplog):
    """Capture dvsim's own logger, which deliberately does not propagate."""
    logger = logging.getLogger("dvsim")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.ERROR, logger="dvsim")
    yield caplog
    logger.removeHandler(caplog.handler)


class TestRunCmd:
    """Test run_cmd."""

    @staticmethod
    def test_returns_output() -> None:
        """Return the command's output when it succeeds."""
        assert_that(run_cmd("echo hello"), equal_to("hello"))

    @staticmethod
    def test_reports_the_failure(dvsim_log) -> None:
        """Log the status and the command's own diagnostic before exiting.

        getstatusoutput folds stderr into the output, so this is the only place a failing
        command's message exists. A flow config that guards a missing tool with
        ${VAR:?message} relies on it reaching the user.
        """
        with pytest.raises(SystemExit) as excinfo:
            run_cmd('echo "set VERILATOR to Verilator 5.052 or newer" >&2; exit 127')

        assert_that(excinfo.value.code, equal_to(127))
        assert_that(dvsim_log.text, contains_string("127"))
        assert_that(dvsim_log.text, contains_string("set VERILATOR to Verilator 5.052 or newer"))

    @staticmethod
    def test_keeps_only_the_tail_of_long_output(dvsim_log) -> None:
        """Log the last lines of a chatty failure, and say how many were left out.

        An {eval_cmd} that shells out to find or to a script can print a great deal before it
        fails, and the error is almost always at the end.
        """
        with pytest.raises(SystemExit):
            run_cmd("seq 1 100 >&2; exit 1")

        assert_that(dvsim_log.text, contains_string("Last 20 of 100 output lines"))
        assert_that(dvsim_log.text, contains_string("100"))
        assert_that(dvsim_log.text, contains_string("81"))
        assert_that(dvsim_log.text, is_not(contains_string("\n80\n")))

    @staticmethod
    def test_quiet_when_there_is_no_output(dvsim_log) -> None:
        """Report the status without an empty second line when the command said nothing."""
        with pytest.raises(SystemExit):
            run_cmd("exit 3")

        assert_that(dvsim_log.text, contains_string("status 3"))
        assert_that(dvsim_log.text.rstrip().count("\n"), equal_to(0))
        assert_that(dvsim_log.text, is_not(contains_string("None")))
