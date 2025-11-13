# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA tool plugin providing VCS support to DVSim."""

import re
from collections.abc import Sequence
from pathlib import Path

__all__ = ("VCS",)


class VCS:
    """Implement VCS tool support."""

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
                match = re.match("total coverage summary", line, re.IGNORECASE)
                if match:
                    # Metrics on the next line.
                    line = buf.readline().strip()
                    metrics = line.split()
                    # Values on the next.
                    line = buf.readline().strip()
                    # Pretty up the values - add % sign for ease of post
                    # processing.
                    values = []
                    for val in line.split():
                        val += " %"
                        values.append(val)
                    # first row is coverage total
                    cov_total = values[0]
                    return [metrics, values], cov_total

        # If we reached here, then we were unable to extract the coverage.
        msg = f"Coverage data not found in {cov_report_path}!"
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
        pattern = r"^CPU [tT]ime:\s*(\d+\.?\d*?)\s*(seconds|minutes|hours).*$"
        for line in reversed(log_text):
            m = re.search(pattern, line)
            if m:
                return float(m.group(1)), m.group(2)[0]
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
        pattern = re.compile(r"^Time:\s*(\d+\.?\d*?)\s*(.?[sS])\s*$")

        for line in reversed(log_text):
            if "V C S   S i m u l a t i o n   R e p o r t" in line:
                raise RuntimeError("Header found before sim time value")

            if m := pattern.search(line):
                return float(m.group(1)), m.group(2).lower()

        msg = "Simulated time not found in the log."
        raise RuntimeError(msg)
