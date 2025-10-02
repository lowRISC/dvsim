# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Report repositories.

Reports are generated as part of a DVSim run and published to a repository.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict
from tabulate import tabulate

from dvsim.report.index import gen_top_level_index


class ReportRepository(BaseModel):
    """Results report configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    publish_path: str
    rclone_env: Mapping = {}

    def refresh_index(self) -> None:
        """Refresh the index files."""
        gen_top_level_index(
            base_path=self.publish_path,
            extra_env=self.rclone_env,
        )


class ReportRepositoriesCollection(BaseModel):
    """Definition of report repositories."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repositories: Mapping[str, ReportRepository] = {}

    def summary(self) -> str:
        """Generate summary of the repos."""
        return tabulate(
            headers=(
                "name",
                "path",
            ),
            tabular_data=[
                [
                    name,
                    config.publish_path,
                ]
                for name, config in self.repositories.items()
            ],
        )
