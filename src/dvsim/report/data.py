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
    variant: str | None = None
    commit: str
    branch: str
    url: str


class ResultsSummary(BaseModel):
    """Summary of results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    top: IPMeta
    """Meta data for the top level config."""

    timestamp: datetime
    """Run time stamp."""

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
