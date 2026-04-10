# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA tool plugin providing Z01X support to DVSim."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from dvsim.sim.tool.vcs import VCS

if TYPE_CHECKING:
    from dvsim.job.deploy import Deploy

__all__ = ("Z01X",)


class Z01X(VCS):
    """Implement Z01X tool support."""

    RUNTIME_COL = 2
    SIMTIME_COL = 3
    REQUIRED_COLS = max(RUNTIME_COL, SIMTIME_COL) + 1

    @staticmethod
    def _get_execution_summary(log_text: Sequence[str]) -> list[str]:
        summary_start: int | None = None
        summary_end: int | None = None
        for i, line in reversed(list(enumerate(log_text))):
            if line.strip() == "Execution Summary":
                summary_start = i
                break
            if summary_end is None and set(line) == set("="):
                summary_end = i
        if summary_start is None:
            msg = f"Execution summary not found in log (start={summary_start}, end={summary_end})"
            raise RuntimeError(msg)

        for line in reversed(log_text[summary_start + 1 : summary_end]):
            if "|" not in line:
                continue
            return [c.strip() for c in line.split("|")]

        msg = f"Summary table not found in log (start={summary_start}, end={summary_end})"
        raise RuntimeError(msg)

    @staticmethod
    def get_job_runtime(log_text: Sequence[str]) -> tuple[float, str]:
        """Return the job runtime (wall clock time) along with its units.

        EDA tools indicate how long the job ran in terms of CPU time in the log
        file. This method invokes the tool specific method which parses the log
        text and returns the runtime as a floating point value followed by its
        units as a tuple.

        Args:
            log_text: is the job's log file contents as a list of lines.

        Returns:
            a tuple of (runtime, units).

        Raises:
            RuntimeError: exception if the search pattern is not found.

        """
        summary_totals = Z01X._get_execution_summary(log_text)
        if len(summary_totals) < Z01X.REQUIRED_COLS:
            msg = f"Summary table contained less columns ({len(summary_totals)}) than expected"
            raise RuntimeError(msg)

        try:  # Quite fragile: columns are hardcoded.
            return float(summary_totals[Z01X.RUNTIME_COL]), "s"
        except ValueError as e:
            msg = f"Found invalid runtime value '{summary_totals[Z01X.RUNTIME_COL]}'"
            raise RuntimeError(msg) from e

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
            a tuple of (simulated time, units).

        Raises:
            RuntimeError: exception if the search pattern is not found.

        """
        summary_totals = Z01X._get_execution_summary(log_text)
        if len(summary_totals) < Z01X.REQUIRED_COLS:
            msg = f"Summary table contained less columns ({len(summary_totals)}) than expected"
            raise RuntimeError(msg)

        try:  # Quite fragile: columns are hardcoded.
            return float(summary_totals[Z01X.SIMTIME_COL]), "s"
        except ValueError as e:
            msg = f"Found invalid simulated time value '{summary_totals[Z01X.SIMTIME_COL]}'"
            raise RuntimeError(msg) from e

    @staticmethod
    def set_additional_attrs(deploy: "Deploy") -> None:
        """Define any additional tool-specific attrs on the deploy object.

        Args:
            deploy: the deploy object to mutate.

        """
        # TODO: when circular import issues are resolved, this can be a check of
        # `isinstance(deploy, RunTest)` and we don't need the type ignores here.
        if deploy.target == "run":
            sim_run_opts = " ".join(opt.strip() for opt in deploy.run_opts)  # type: ignore[reportAttributeAccessIssue]
            deploy.exports.append({"sim_run_opts": sim_run_opts})
            deploy.run_opts = list(getattr(deploy.sim_cfg, "run_opts_fi_sim", ()))  # type: ignore[reportAttributeAccessIssue]
