# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Simulation data models."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from dvsim.report.data import IPMeta, ToolMeta
from dvsim.sim_results import BucketedFailures

__all__ = (
    "CodeCoverageMetrics",
    "CoverageMetrics",
    "SimFlowResults",
    "SimResultsSummary",
    "TestResult",
    "TestStage",
    "Testpoint",
)


class TestResult(BaseModel):
    """Test result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_time: float
    """Run time."""
    sim_time: float
    """Simulation time."""

    passed: int
    """Number of tests passed."""
    total: int
    """Total number of tests run."""
    percent: float
    """Percentage test pass rate."""


class Testpoint(BaseModel):
    """Testpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tests: Mapping[str, TestResult]
    """Test results."""

    passed: int
    """Number of tests passed."""
    total: int
    """Total number of tests run."""
    percent: float
    """Percentage test pass rate."""


class TestStage(BaseModel):
    """Test stages."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    testpoints: Mapping[str, Testpoint]
    """Results by test point."""

    passed: int
    """Number of tests passed."""
    total: int
    """Total number of tests run."""
    percent: float
    """Percentage test pass rate."""


class CodeCoverageMetrics(BaseModel):
    """CodeCoverage metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    block: float | None
    """Block Coverage (%) - did this part of the code execute?"""
    line_statement: float | None
    """Line/Statement Coverage (%) - did this part of the code execute?"""
    branch: float | None
    """Branch Coverage (%) - did this if/case take all paths?"""
    condition_expression: float | None
    """Condition/Expression Coverage (%) - did the logic evaluate to 0 & 1?"""
    toggle: float | None
    """Toggle Coverage (%) - did the signal wiggle?"""
    fsm: float | None
    """FSM Coverage (%) - did the state machine transition?"""

    @property
    def average(self) -> float | None:
        """Average code coverage (%)."""
        all_cov = [
            c
            for c in [
                self.line_statement,
                self.branch,
                self.condition_expression,
                self.toggle,
                self.fsm,
            ]
            if c is not None
        ]

        if len(all_cov) == 0:
            return None

        return sum(all_cov) / len(all_cov)


class CoverageMetrics(BaseModel):
    """Coverage metrics."""

    code: CodeCoverageMetrics | None
    """Code Coverage."""
    assertion: float | None
    """Assertion Coverage."""
    functional: float | None
    """Functional coverage."""

    @property
    def average(self) -> float | None:
        """Average code coverage (%) or None if there is no coverage."""
        code = self.code.average if self.code is not None else None
        all_cov = [
            c
            for c in [
                code,
                self.assertion,
                self.functional,
            ]
            if c is not None
        ]

        if len(all_cov) == 0:
            return None

        return sum(all_cov) / len(all_cov)


class FlowResults(BaseModel):
    """Flow results data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    block: IPMeta
    """IP block metadata."""
    tool: ToolMeta
    """Tool used in the simulation run."""
    timestamp: datetime
    """Timestamp for when the test ran."""

    stages: Mapping[str, TestStage]
    """Results per test stage."""
    coverage: CoverageMetrics | None
    """Coverage metrics."""

    failed_jobs: BucketedFailures
    """Bucketed failed job overview."""

    passed: int
    """Number of tests passed."""
    total: int
    """Total number of tests run."""
    percent: float
    """Percentage test pass rate."""

    @staticmethod
    def load(path: Path) -> "FlowResults":
        """Load results from JSON file.

        Transform the fields of the loaded JSON into a more useful schema for
        report generation.

        Args:
            path: to the json file to load.

        """
        return FlowResults.model_validate_json(path.read_text())


class SimFlowResults(BaseModel):
    """Flow results data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    block: IPMeta
    """IP block metadata."""
    tool: ToolMeta
    """Tool used in the simulation run."""
    timestamp: datetime
    """Timestamp for when the test ran."""

    stages: Mapping[str, TestStage]
    """Results per test stage."""
    coverage: CoverageMetrics | None
    """Coverage metrics."""

    failed_jobs: BucketedFailures
    """Bucketed failed job overview."""

    passed: int
    """Number of tests passed."""
    total: int
    """Total number of tests run."""
    percent: float
    """Percentage test pass rate."""

    @staticmethod
    def load(path: Path) -> "FlowResults":
        """Load results from JSON file.

        Transform the fields of the loaded JSON into a more useful schema for
        report generation.

        Args:
            path: to the json file to load.

        """
        return FlowResults.model_validate_json(path.read_text())


class SimResultsSummary(BaseModel):
    """Summary of results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    top: IPMeta
    """Meta data for the top level config."""

    timestamp: datetime
    """Run time stamp."""

    flow_results: Mapping[str, SimFlowResults]
    """Flow results."""

    report_path: Path
    """Path to the report JSON file."""

    @staticmethod
    def load(path: Path) -> "SimResultsSummary":
        """Load results from JSON file.

        Transform the fields of the loaded JSON into a more useful schema for
        report generation.

        Args:
            path: to the json file to load.

        Returns:
            The loaded ResultsSummary from JSON.

        """
        return SimResultsSummary.model_validate_json(path.read_text())
