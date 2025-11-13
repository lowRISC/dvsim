# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA tool plugin providing Xcelium support to DVSim."""

import re
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path

__all__ = ("Xcelium",)


class Xcelium:
    """Implement Xcelium tool support."""

    @staticmethod
    def get_cov_summary_table(cov_report_path: Path) -> tuple[Sequence[Sequence[str]], str]:
        """Get a coverage summary.

        Args:
            cov_report_path: path to the raw coverage report

        Returns:
            tuple of, List of metrics and values, and final coverage total

        """
        with Path(cov_report_path).open() as buf:
            for line in buf:
                if "name" in line:
                    # Strip the line and remove the unwanted "* Covered" string.
                    metrics = line.strip().replace("* Covered", "").split()
                    # Change first item to 'Score'.
                    metrics[0] = "Score"

                    # Gather the list of metrics.
                    items = OrderedDict()
                    for metric in metrics:
                        items[metric] = {}
                        items[metric]["covered"] = 0
                        items[metric]["total"] = 0

                    # Next line is a separator.
                    line = buf.readline()

                    # Subsequent lines are coverage items to be aggregated.
                    for line in buf:
                        line = re.sub(r"%\s+\(", "%(", line)
                        values = line.strip().split()
                        for i, value in enumerate(values):
                            value = value.strip()
                            m = re.search(r"\((\d+)/(\d+).*\)", value)
                            if m:
                                items[metrics[i]]["covered"] += int(m.group(1))
                                items[metrics[i]]["total"] += int(m.group(2))
                                items["Score"]["covered"] += int(m.group(1))
                                items["Score"]["total"] += int(m.group(2))

                    # Capture the percentages and the aggregate.
                    values = []
                    cov_total = None
                    for metric in items:
                        if items[metric]["total"] == 0:
                            values.append("-- %")
                        else:
                            value = items[metric]["covered"] / items[metric]["total"] * 100
                            value = f"{round(value, 2):.2f} %"
                            values.append(value)
                            if metric == "Score":
                                cov_total = value

                    return [items.keys(), values], cov_total

        # If we reached here, then we were unable to extract the coverage.
        msg = f"Coverage data not found in {buf.name}!"
        raise SyntaxError(msg)

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
        pattern = r"^TOOL:\s*xrun.*: Exiting on .*\(total:\s*(\d+):(\d+):(\d+)\)\s*$"
        for line in reversed(log_text):
            if m := re.search(pattern, line):
                t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                return t, "s"

        msg = "Job runtime not found in the log."
        raise RuntimeError(msg)

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
        pattern = r"^Simulation complete .* at time (\d+\.?\d*?)\s*(.?[sS]).*$"
        for line in reversed(log_text):
            if m := re.search(pattern, line):
                return float(m.group(1)), m.group(2).lower()

        msg = "Simulated time not found in the log."
        raise RuntimeError(msg)
