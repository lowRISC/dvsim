# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim cli."""

import pytest
from hamcrest import assert_that, calling, contains_string, equal_to, raises

from dvsim.cli import main
from dvsim.cli.run import resolve_max_parallel


def test_cli() -> None:
    """Test that the CLI can be called without args.

    This doesn't test anything specific, only that the cli module can be
    imported without errors and main function executes without errors. The
    expectation is that a usage message is presented.
    """
    assert_that(calling(main).with_args(), raises(SystemExit))


@pytest.mark.parametrize(
    ("cpus", "max_parallel"),
    [(1, 1), (2, 1), (4, 3), (17, 16), (18, 16), (64, 16), (None, 16)],
)
def test_default_max_parallel(
    monkeypatch: pytest.MonkeyPatch,
    dvsim_log: pytest.LogCaptureFixture,
    cpus: int | None,
    max_parallel: int,
) -> None:
    """Test that the default is one less than the logical CPUs, up to a maximum of 16."""
    monkeypatch.delenv("DVSIM_MAX_PARALLEL", raising=False)
    monkeypatch.setattr("os.cpu_count", lambda: cpus)

    assert_that(resolve_max_parallel(None), equal_to(max_parallel))
    assert_that(dvsim_log.messages[-1], contains_string(f"max_parallel={max_parallel}"))
