# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA tool plugin providing Verilator support to DVSim."""

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from dvsim.job.data import JobSpec
from dvsim.sim.data import CodeCoverageMetrics, CoverageMetrics
from dvsim.sim.tool.base import VersionQuery

if TYPE_CHECKING:
    from dvsim.job.deploy import Deploy

__all__ = ("Verilator",)

_COV_METRIC_RE = re.compile(
    r"^\s*(line|toggle|branch|expr|fsm_state|fsm_arc|user)\s*:\s*"
    r"\d+(?:\.\d+)?%\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)\s*$",
)


class Verilator:
    """Implement Verilator tool support.

    Verilator differs from the commercial simulators in ways this plugin has to
    absorb:

    - The build step produces a standalone executable rather than a tool
      database, so the run step is that executable and not the tool again.
    - Build and run timing use different Verilator footer formats.
    - Coverage metric names differ from DVSim's internal names.
    """

    # `verilator --version` reports a single line, either
    # "Verilator v5.052 (2026-09-06)" for a release or
    # "Verilator 5.053 devel rev vUNKNOWN-built19800101" for a local build.
    # Capture the whole line after the tool name and optional release-only `v`:
    # the number alone does not distinguish a development build from the release
    # it sits on, and the revision is worth recording during flow bring-up.
    version_query: ClassVar[VersionQuery | None] = VersionQuery(
        cmd="verilator --version",
        pattern=r"^Verilator\s+v?(\S.*?)\s*$",
    )

    @staticmethod
    def get_cov_summary_table(cov_report_path: Path) -> tuple[Sequence[Sequence[str]], str]:
        """Get a coverage summary.

        Parse `verilator_coverage --report summary` output.

        Args:
            cov_report_path: path to the raw coverage report

        Returns:
            tuple of, List of metrics and values, and final coverage total

        """
        raw_metrics: dict[str, tuple[int, int]] = {}
        in_summary = False
        with cov_report_path.open() as buf:
            for line in buf:
                if line.strip() == "Coverage Summary:":
                    in_summary = True
                    continue
                if not in_summary:
                    continue
                if match := _COV_METRIC_RE.match(line):
                    raw_metrics[match.group(1)] = (int(match.group(2)), int(match.group(3)))
                elif raw_metrics:
                    break

        if not raw_metrics:
            msg = f"Coverage data not found in {cov_report_path}!"
            raise RuntimeError(msg)

        metric_groups = (
            ("Line", ("line",)),
            ("Toggle", ("toggle",)),
            ("Branch", ("branch",)),
            ("Expr", ("expr",)),
            ("FSM", ("fsm_state", "fsm_arc")),
            ("User", ("user",)),
        )
        headers = ["Score"]
        values: list[str] = []
        score_covered = 0
        score_total = 0
        for header, metric_names in metric_groups:
            present = [raw_metrics[name] for name in metric_names if name in raw_metrics]
            if not present:
                continue
            covered = sum(item[0] for item in present)
            total = sum(item[1] for item in present)
            headers.append(header)
            values.append("-- %" if total == 0 else f"{covered / total * 100:.2f} %")
            score_covered += covered
            score_total += total

        cov_total = "-- %" if score_total == 0 else f"{score_covered / score_total * 100:.2f} %"
        return [headers, [cov_total, *values]], cov_total

    @staticmethod
    def get_job_runtime(_job: JobSpec, log_text: Sequence[str]) -> tuple[float, str]:
        """Return the job runtime (wall clock time) along with its units.

        EDA tools indicate how long the job ran in terms of CPU time in the log
        file. This method invokes the tool specific method which parses the log
        text and returns the runtime as a floating point value followed by its
        units as a tuple.

        Args:
            job: The job that was run.
            log_text: is the job's log file contents as a list of lines.

        Returns:
            a tuple of (runtime, units).

        Raises:
            RuntimeError: exception if the search pattern is not found.

        """
        build_pattern = re.compile(r"^- Verilator: Walltime\s+(\d+\.?\d*)\s*s\b")
        run_pattern = re.compile(
            r"^- Verilator: \$(?:finish|stop) at \d+\.?\d*[munpf]?s; "
            r"walltime (\d+\.?\d*) s\b",
        )

        for line in reversed(log_text):
            if m := build_pattern.search(line):
                return float(m.group(1)), "s"
            if m := run_pattern.search(line):
                return float(m.group(1)), "s"

        msg = "Job runtime not found in the log."
        raise RuntimeError(msg)

    @staticmethod
    def get_simulated_time(_job: JobSpec, log_text: Sequence[str]) -> tuple[float, str]:
        """Return the simulated time along with its units.

        EDA tools indicate how long the design was simulated for in the log file.
        This method invokes the tool specific method which parses the log text and
        returns the simulated time as a floating point value followed by its
        units (typically, pico|nano|micro|milliseconds) as a tuple.

        Args:
            job: The job that was run
            log_text: is the job's log file contents as a list of lines.

        Returns:
            a tuple of (simulated time, units).

        Raises:
            RuntimeError: exception if the search pattern is not found.

        """
        patterns = (
            re.compile(
                r"^- Verilator: \$(?:finish|stop) at (\d+\.?\d*)([munpf]?s); walltime\b",
            ),
            re.compile(r"^Time:\s*(\d+\.?\d*)\s*([munpf]?s)\b", re.IGNORECASE),
        )
        for line in reversed(log_text):
            for pattern in patterns:
                if m := pattern.search(line):
                    return float(m.group(1)), m.group(2).lower()

        msg = "Simulated time not found in the log."
        raise RuntimeError(msg)

    @staticmethod
    def get_coverage_metrics(raw_metrics: Mapping[str, float | None] | None) -> CoverageMetrics:
        """Get a CoverageMetrics model from raw coverage data.

        Verilator reports covergroups as user coverage. RTL assertions are not
        enabled in the supported flow, so assertion coverage remains absent.

        Args:
            raw_metrics: raw coverage metrics as parsed from the tool.

        Returns:
            CoverageMetrics model.

        """
        if raw_metrics is None:
            return CoverageMetrics(code=None, assertion=None, functional=None)

        return CoverageMetrics(
            functional=raw_metrics.get("user"),
            assertion=None,
            code=CodeCoverageMetrics(
                block=None,
                line_statement=raw_metrics.get("line"),
                branch=raw_metrics.get("branch"),
                condition_expression=raw_metrics.get("expr"),
                toggle=raw_metrics.get("toggle"),
                fsm=raw_metrics.get("fsm"),
            ),
        )

    @staticmethod
    def set_additional_attrs(deploy: "Deploy") -> None:
        """Define any additional tool-specific attrs on the deploy object.

        Args:
            deploy: the deploy object to mutate.

        """
