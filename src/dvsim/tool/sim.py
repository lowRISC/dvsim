# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA simulation tool interface."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = ("SimTool",)


@runtime_checkable
class SimTool(Protocol):
    """Simulation tool interface required by the Sim workflow."""

    @staticmethod
    def get_cov_summary_table(cov_report_path: Path) -> tuple[Sequence[Sequence[str]], str]:
        """Get a coverage summary.

        Args:
            cov_report_path: path to the raw coverage report

        Returns:
            tuple of, List of metrics and values, and final coverage total

        """
        ...

    @staticmethod
    def get_job_runtime(log_text: Sequence[str]) -> tuple[float, str]:
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

        """
        ...

    @staticmethod
    def get_simulated_time(log_text: Sequence[str]) -> tuple[float, str]:
        """Return the simulated time along with its units.

        EDA tools indicate how long the design was simulated for in the log file.
        This method invokes the tool specific method which parses the log text and
        returns the simulated time as a floating point value followed by its
        units (typically, pico|nano|micro|milliseconds) as a tuple.

        Args:
            log_text: is the job's log file contents as a list of lines.

        Returns:
            the simulated, units as a tuple.

        Raises:
            RuntimeError: exception if the search pattern is not found.

        """
        ...
