# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the Verilator tool plugin."""

from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to

from dvsim.sim.data import CodeCoverageMetrics, CoverageMetrics
from dvsim.sim.tool.verilator import Verilator
from tests.test_scheduler import job_spec_factory

__all__ = ("TestVerilatorToolPlugin",)


class TestVerilatorToolPlugin:
    """Test Verilator log and coverage parsing."""

    @staticmethod
    def test_get_cov_summary_table(tmp_path: Path) -> None:
        """Parse every coverage metric and combine the two FSM rows."""
        report = tmp_path / "coverage.txt"
        report.write_text(
            """\
Coverage Summary:
  line      : 80.0% ( 8/10)
  toggle    : 50.0% ( 5/10)
  branch    : 75.0% ( 3/ 4)
  expr      : 100.0% ( 2/ 2)
  fsm_state : 100.0% ( 2/ 2)
  fsm_arc   : 50.0% ( 1/ 2)
  user      : 100.0% ( 4/ 4)
""",
        )

        assert_that(
            Verilator.get_cov_summary_table(report),
            equal_to(
                (
                    [
                        ["Score", "Line", "Toggle", "Branch", "Expr", "FSM", "User"],
                        [
                            "73.53 %",
                            "80.00 %",
                            "50.00 %",
                            "75.00 %",
                            "100.00 %",
                            "75.00 %",
                            "100.00 %",
                        ],
                    ],
                    "73.53 %",
                ),
            ),
        )

    @staticmethod
    def test_get_cov_summary_table_ignores_metrics_without_points(tmp_path: Path) -> None:
        """Report an unavailable metric without including it in the total."""
        report = tmp_path / "coverage.txt"
        report.write_text(
            """\
Coverage Summary:
  line      : 50.0% (1/2)
  fsm_state : 0.0% (0/0)
  fsm_arc   : 0.0% (0/0)
""",
        )

        assert_that(
            Verilator.get_cov_summary_table(report),
            equal_to(
                (
                    [["Score", "Line", "FSM"], ["50.00 %", "50.00 %", "-- %"]],
                    "50.00 %",
                ),
            ),
        )

    @staticmethod
    def test_get_cov_summary_table_rejects_missing_summary(tmp_path: Path) -> None:
        """Reject a report without a coverage summary."""
        report = tmp_path / "coverage.txt"
        report.write_text("No coverage here\n")

        with pytest.raises(RuntimeError, match="Coverage data not found"):
            Verilator.get_cov_summary_table(report)

    @staticmethod
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("- Verilator: Walltime 442.667 s (elab=14.410); cpu 194.280 s", (442.667, "s")),
            (
                "- Verilator: $finish at 545us; walltime 20.321 s; speed 26.809 us/s",
                (20.321, "s"),
            ),
        ],
    )
    def test_get_job_runtime(tmp_path: Path, line: str, expected: tuple[float, str]) -> None:
        """Parse build and run wall-time footers."""
        assert_that(
            Verilator.get_job_runtime(job_spec_factory(tmp_path), [line]),
            equal_to(expected),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("- Verilator: $finish at 545us; walltime 20.321 s; speed 26.809 us/s", (545.0, "us")),
            ("Time: 1234 ns", (1234.0, "ns")),
        ],
    )
    def test_get_simulated_time(tmp_path: Path, line: str, expected: tuple[float, str]) -> None:
        """Parse Verilator and UVM simulation-time formats."""
        assert_that(
            Verilator.get_simulated_time(job_spec_factory(tmp_path), [line]),
            equal_to(expected),
        )

    @staticmethod
    def test_get_coverage_metrics() -> None:
        """Map Verilator metric names to the DVSim coverage model."""
        assert_that(
            Verilator.get_coverage_metrics(
                {
                    "line": 80.0,
                    "toggle": 50.0,
                    "branch": 75.0,
                    "expr": 100.0,
                    "fsm": 75.0,
                    "user": 100.0,
                },
            ),
            equal_to(
                CoverageMetrics(
                    functional=100.0,
                    assertion=None,
                    code=CodeCoverageMetrics(
                        block=None,
                        line_statement=80.0,
                        branch=75.0,
                        condition_expression=100.0,
                        toggle=50.0,
                        fsm=75.0,
                    ),
                ),
            ),
        )
