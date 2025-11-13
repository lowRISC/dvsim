# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the EDA tool utilities."""

import pytest
from hamcrest import assert_that, equal_to, instance_of

from dvsim.tool.sim import SimTool
from dvsim.tool.utils import _SUPPORTED_SIM_TOOLS, get_sim_tool_plugin

__all__ = ("TestEDAToolPlugins",)


class TestEDAToolPlugins:
    """Test the EDA tool plug-ins."""

    @staticmethod
    @pytest.mark.parametrize("tool", _SUPPORTED_SIM_TOOLS.keys())
    def test_get_sim_tool_plugin(tool: str) -> None:
        """Test that sim plugins can be retrieved correctly."""
        assert_that(
            get_sim_tool_plugin(tool),
            equal_to(_SUPPORTED_SIM_TOOLS[tool]),
        )

    @staticmethod
    @pytest.mark.parametrize("tool", _SUPPORTED_SIM_TOOLS.keys())
    def test_plugins_implement_simtool_protocol(tool: str) -> None:
        """Test that all sim plugins implement the SimTool interface."""
        plugin = get_sim_tool_plugin(tool)

        assert_that(plugin, instance_of(SimTool))
