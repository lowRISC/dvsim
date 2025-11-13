# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA Tool base."""

from dvsim.logging import log
from dvsim.tool.sim import SimTool
from dvsim.tool.vcs import VCS
from dvsim.tool.xcelium import Xcelium

__all__ = ("get_sim_tool_plugin",)

_SUPPORTED_SIM_TOOLS = {
    "vcs": VCS,
    "xcelium": Xcelium,
}


def get_sim_tool_plugin(tool: str) -> SimTool:
    """Get a simulation tool plugin."""
    if tool not in _SUPPORTED_SIM_TOOLS:
        log.error(
            "Unsupported tool '%s', please use one of [%s]",
            tool,
            ",".join(_SUPPORTED_SIM_TOOLS.keys()),
        )
        msg = f"{tool} not supported"
        raise NotImplementedError(msg)

    return _SUPPORTED_SIM_TOOLS[tool]
