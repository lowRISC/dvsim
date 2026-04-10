# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the VCS tool plugin."""

from collections.abc import Sequence
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to

from dvsim.tool.utils import get_sim_tool_plugin
from tests.test_scheduler import job_spec_factory

__all__ = ("TestVCSToolPlugin",)


def fake_log(sim_time: float = 1, sim_time_units: str = "s") -> Sequence[str]:
    """Fabricate a log."""
    return [
        "Other",
        "log",
        "content",
        "",
        "     V C S   S i m u l a t i o n   R e p o r t    ",
        f"Time: {sim_time} {sim_time_units}",
    ]


class TestVCSToolPlugin:
    """Test the VCS tool plug-in."""

    @staticmethod
    @pytest.mark.parametrize(
        ("time", "units"),
        [
            (1.2, "s"),
            (2.12, "ps"),
            (3.73, "S"),
            (4.235, "pS"),
            (5.5134, "PS"),
        ],
    )
    def test_get_simulated_time(tmp_path: Path, time: int, units: str) -> None:
        """Test that sim plugins can be retrieved correctly."""
        plugin = get_sim_tool_plugin("vcs")
        mock_job_spec = job_spec_factory(tmp_path)

        assert_that(
            plugin.get_simulated_time(
                mock_job_spec,
                log_text=fake_log(
                    sim_time=time,
                    sim_time_units=units,
                ),
            ),
            equal_to((time, units.lower())),
        )
