# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Report data models."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

__all__ = (
    "IPMeta",
    "ResultsSummary",
)


class IPMeta(BaseModel):
    """Meta data for an IP block."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the IP."""
    variant: str | None = None
    """Variant of the IP if there is one."""

    commit: str
    """Git commit sha of the IP the tests are run against."""
    branch: str
    """Git branch"""
    url: str
    """URL to where the IP can be found in git (e.g. github)."""


class ToolMeta(BaseModel):
    """Meta data for an EDA tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the tool."""
    version: str
    """Version of the tool."""


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
    coverage: Mapping[str, float | None]
    """Coverage metrics."""

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


class ResultsSummary(BaseModel):
    """Summary of results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    top: IPMeta
    """Meta data for the top level config."""

    timestamp: datetime
    """Run time stamp."""

    flow_results: Mapping[str, FlowResults]
    """Flow results."""

    report_index: Mapping[str, Path]
    """Index of the IP block reports."""

    report_path: Path
    """Path to the report JSON file."""

    @staticmethod
    def load(path: Path) -> "ResultsSummary":
        """Load results from JSON file.

        Transform the fields of the loaded JSON into a more useful schema for
        report generation.

        Args:
            path: to the json file to load.

        Returns:
            The loaded ResultsSummary from JSON.

        """
        return ResultsSummary.model_validate_json(path.read_text())
