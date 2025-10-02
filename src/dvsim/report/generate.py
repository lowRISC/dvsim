# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate reports."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from dvsim.logging import log
from dvsim.project import Project
from dvsim.templates.render import render_template

__all__ = ("generate_report",)


class _FlowResultsOrig(BaseModel):
    """Results data as stored in the JSON file.

    This class is here for the sake of providing a schema for the current JSON
    report format. However this should be unesesery when the format of the JSON
    file matches the FlowResults model.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    block_name: str
    block_variant: str | None
    report_timestamp: str
    git_revision: str
    git_branch_name: str
    report_type: str
    tool: str
    results: Mapping


class IPMeta(BaseModel):
    """Meta data for an IP block."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    variant: str | None = None
    commit: str
    branch: str
    url: str


class ToolMeta(BaseModel):
    """Meta data for an EDA tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str


class TestResult(BaseModel):
    """Test result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_time: int
    sim_time: int
    passed: int
    total: int
    percent: float


class Testpoint(BaseModel):
    """Testpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tests: Mapping[str, TestResult]

    passed: int
    total: int
    percent: float


class TestStage(BaseModel):
    """Test stages."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    testpoints: Mapping[str, Testpoint]

    passed: int
    total: int
    percent: float


class FlowResults(BaseModel):
    """Flow results data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    block: IPMeta
    tool: ToolMeta
    timestamp: datetime

    stages: Mapping[str, TestStage]
    coverage: Mapping[str, float]

    passed: int
    total: int
    percent: float

    @staticmethod
    def load(path: Path) -> "FlowResults":
        """Load results from JSON file.

        Transform the fields of the loaded JSON into a more useful schema for
        report generation.

        Args:
            path: to the json file to load.
        """
        results = _FlowResultsOrig.model_validate_json(path.read_text())

        # Pull out the test results per stage
        stages = {}
        for testpoint_data in results.results["testpoints"]:
            stage = testpoint_data["stage"]
            testpoint = testpoint_data["name"]
            tests = testpoint_data["tests"]

            if stage not in stages:
                stages[stage] = {"testpoints": {}}

            stages[stage]["testpoints"][testpoint] = {
                "tests": {
                    test["name"]: {
                        "max_time": test["max_runtime_s"],
                        "sim_time": test["simulated_time_us"],
                        "passed": test["passing_runs"],
                        "total": test["total_runs"],
                        "percent": 100 * test["passing_runs"] / test["total_runs"],
                    }
                    for test in tests
                },
            }

        # unmapped tests that are not part of the test plan?
        # Why are they not part of a test plan?
        if results.results["unmapped_tests"]:
            stages["unmapped"] = {
                "testpoints": {
                    "None": {
                        "tests": {
                            test["name"]: {
                                "max_time": test["max_runtime_s"],
                                "sim_time": test["simulated_time_us"],
                                "passed": test["passing_runs"],
                                "total": test["total_runs"],
                                "percent": 100 * test["passing_runs"] / test["total_runs"],
                            }
                            for test in results.results["unmapped_tests"]
                        },
                    },
                },
            }

        # Gather stats
        f_total = 0
        f_passed = 0
        for stage in stages:  # noqa: PLC0206
            s_total = 0
            s_passed = 0

            for testpoint in stages[stage]["testpoints"]:
                tp_total = 0
                tp_passed = 0
                tp_data = stages[stage]["testpoints"][testpoint]

                for test in tp_data["tests"].values():
                    tp_total += test["total"]
                    tp_passed += test["passed"]

                s_total += tp_total
                s_passed += tp_passed
                tp_data["total"] = tp_total
                tp_data["passed"] = tp_passed
                tp_data["percent"] = 100 * tp_passed / tp_total

            f_total += s_total
            f_passed += s_passed
            stages[stage]["total"] = s_total
            stages[stage]["passed"] = s_passed
            stages[stage]["percent"] = 100 * s_passed / s_total

        return FlowResults(
            block=IPMeta(
                name=results.block_name,
                variant=results.block_variant,
                commit=results.git_revision,
                branch=results.git_branch_name,
                url=f"https://github.com/lowrisc/opentitan/tree/{results.git_revision}",
            ),
            tool=ToolMeta(
                name=results.tool,
                version="???",
            ),
            timestamp=results.report_timestamp,
            stages=stages,
            passed=f_passed,
            total=f_total,
            percent=100 * f_passed / f_total,
            coverage=results.results["coverage"],
        )


class ResultsSummary(BaseModel):
    """Summary of results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    top: IPMeta
    timestamp: datetime

    flow_results: Mapping[str, FlowResults]
    report_index: Mapping[str, Path]
    report_path: Path

    @staticmethod
    def load(path: Path) -> "ResultsSummary":
        """Load results from JSON file.

        Transform the fields of the loaded JSON into a more useful schema for
        report generation.

        Args:
            path: to the json file to load.
        """
        return ResultsSummary.model_validate_json(path.read_text())


def generate_report(run_path: Path) -> None:
    """Generate a report."""
    log.info("Generating report for run: %s", run_path)

    project = Project.load(path=run_path)
    config = project.config

    log.debug("%s", config.rel_path)

    reports_dir = project.run_dir / "reports"

    flow_results = {}
    report_index = {}
    for child_cfg in config.cfgs.values():
        report_path = reports_dir / child_cfg.rel_path
        json_path = report_path / "report.json"
        html_path = report_path / "index.html"

        log.debug("loading results from '%s'", json_path)

        results = FlowResults.load(path=json_path)

        gen_block_report(
            results=results,
            path=html_path,
        )

        block_name = results.block.name
        flow_results[block_name] = results
        report_index[block_name] = report_path.relative_to(reports_dir)

    summary_path = reports_dir / project.config.rel_path

    summary = ResultsSummary(
        top=IPMeta(
            name=project.config.name,
            commit="commit",
            branch=project.branch,
            url="url",
        ),
        timestamp=0,
        flow_results=flow_results,
        report_index=report_index,
        report_path=summary_path.relative_to(reports_dir),
    )

    generate_summary_report(
        summary=summary,
        path=summary_path / "index.html",
    )

    (summary_path / "report.json").write_text(
        summary.model_dump_json(),
    )


def gen_block_report(results: FlowResults, path: Path) -> None:
    """Generate a block report."""
    log.debug("generating report '%s'", path)
    path.write_text(
        render_template(
            path=Path("reports") / "block_report.html",
            data={"results": results},
        ),
    )


def generate_summary_report(summary: ResultsSummary, path: Path) -> None:
    """Generate a summary report."""
    log.debug("generating report '%s'", path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_template(
            path=Path("reports") / "summary_report.html",
            data={
                "summary": summary,
            },
        ),
    )
