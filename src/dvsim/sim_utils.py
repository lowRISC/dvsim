# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Common DV simulation specific utilities."""

from collections.abc import Sequence
from pathlib import Path

from dvsim.tool.utils import get_sim_tool_plugin


def get_cov_summary_table(
    txt_cov_report: Path,
    tool: str,
) -> tuple[Sequence[Sequence[str]], str]:
    """Capture the summary results as a list of lists.

    The text coverage report is passed as input to the function, in addition to
    the tool used.

    Returns:
        tuple of, List of metrics and values, and final coverage total

    Raises:
        the appropriate exception if the coverage summary extraction fails.

    """
    plugin = get_sim_tool_plugin(tool)

    return plugin.get_cov_summary_table(cov_report_path=txt_cov_report)


def get_job_runtime(log_text: list, tool: str) -> tuple[float, str]:
    """Return the job runtime (wall clock time) along with its units.

    EDA tools indicate how long the job ran in terms of CPU time in the log
    file. This method invokes the tool specific method which parses the log
    text and returns the runtime as a floating point value followed by its
    units as a tuple.

    Args:
        log_text: is the job's log file contents as a list of lines.
        tool: is the EDA tool used to run the job.

    Returns:
        a tuple of (runtime, units).

    Raises:
        NotImplementedError: exception if the EDA tool is not supported.

    """
    plugin = get_sim_tool_plugin(tool)

    return plugin.get_job_runtime(log_text=log_text)


def get_simulated_time(log_text: list, tool: str) -> tuple[float, str]:
    """Return the simulated time along with its units.

    EDA tools indicate how long the design was simulated for in the log file.
    This method invokes the tool specific method which parses the log text and
    returns the simulated time as a floating point value followed by its
    units (typically, pico|nano|micro|milliseconds) as a tuple.

    Args:
        log_text: is the job's log file contents as a list of lines.
        tool: is the EDA tool used to run the job.

    Returns:
        the simulated, units as a tuple.

    Raises:
        NotImplementedError: exception if the EDA tool is not supported.

    """
    plugin = get_sim_tool_plugin(tool)

    return plugin.get_simulated_time(log_text=log_text)
