# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA Tool base."""

import re
import shlex
import subprocess
from collections.abc import Callable
from functools import cache

from dvsim.logging import log
from dvsim.sim.tool.base import SimTool
from dvsim.sim.tool.vcs import VCS
from dvsim.sim.tool.xcelium import Xcelium
from dvsim.sim.tool.z01x import Z01X

__all__ = ("get_sim_tool_plugin", "query_tool_version")

_SUPPORTED_SIM_TOOLS = {
    "vcs": VCS,
    "xcelium": Xcelium,
    "z01x": Z01X,
}

# EDA tools should respond to a `--version`-style query near-instantly. Add a
# timeout so a hung/misconfigured tool cannot block report generation forever.
# However, allow a significant amount of time to allow for cold fetching from
# a networked filesystem.
_VERSION_QUERY_TIMEOUT_S = 120


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


@cache
def _run_version_command(cmd: str) -> str | None:
    """Run a tool version-query command, returning its combined output or None.

    The tool's version may be printed to either stdout or stderr, so both are
    captured and concatenated. Any failure to launch or run the command (the
    tool is not on PATH, a non-EDA host, a timeout, ...) is treated as "version
    unknown" rather than an error: querying the version must never break a run.

    Results are cached for the lifetime of the process since a tool's version is
    invariant across a single dvsim invocation; this dedupes the query when
    multiple configs share a tool.
    """
    try:
        result = subprocess.run(  # noqa: S603
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=_VERSION_QUERY_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        log.debug("Failed to query tool version via '%s': %s", cmd, e)
        return None

    return result.stdout + result.stderr


def query_tool_version(
    tool: str,
    *,
    run: Callable[[str], str | None] = _run_version_command,
) -> str | None:
    """Query the version of an EDA tool from the runtime environment.

    Runs the tool plugin's declared version-query command and parses the version
    out of its output. This is a local, best-effort probe: it assumes the tool
    is available on PATH of the host running dvsim.

    TODO: for farm launchers (LSF/SGE/SLURM) the tool may only exist on the
    compute nodes. To be correct there, this should run as a lightweight
    preflight job dispatched through the runtime backend so it inherits the same
    environment (e.g. `module load`) as real jobs.

    Args:
        tool: the name of the tool to query (as passed to `--tool`).
        run: callable that executes the query command and returns its combined
            output, or None on failure. Injectable for testing.

    Returns:
        The parsed (non-empty) version string, or None if the tool declares no
        query, the command failed, or the output did not yield a version (no
        match, no capture group, or an empty/whitespace-only capture).

    """
    query = get_sim_tool_plugin(tool).version_query
    if query is None:
        return None

    output = run(query.cmd)
    if output is None:
        return None

    match = re.search(query.pattern, output, re.MULTILINE)
    if match is None:
        log.debug("Could not parse %s version from output of '%s'", tool, query.cmd)
        return None

    try:
        version = match.group(1).strip()
    except IndexError:
        # A missing capture group is a plugin-authoring bug, but querying the
        # version must never break a run, so log it and report "unknown".
        log.error(
            "version_query.pattern for tool '%s' matched but has no capture group; "
            "it must contain one group capturing the version: %r",
            tool,
            query.pattern,
        )
        return None

    if not version:
        # An empty/whitespace capture is not a usable version; treat it as a
        # non-match so callers never see a falsy-but-not-None version string.
        log.debug("Parsed an empty %s version from output of '%s'", tool, query.cmd)
        return None

    return version
