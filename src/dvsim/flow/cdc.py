# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Class describing lint configuration object."""

from argparse import Namespace
from collections.abc import Mapping, Sequence
from pathlib import Path

from dvsim.flow.lint import LintCfg
from dvsim.project import Project


class CdcCfg(LintCfg):
    """Derivative class for linting purposes."""

    flow = "cdc"

    def __init__(
        self,
        flow_cfg_file: Path,
        project_cfg: Project,
        config_data: Mapping,
        args: Namespace,
        child_configs: Sequence["CdcCfg"] | None = None,
    ) -> None:
        super().__init__(
            flow_cfg_file=flow_cfg_file,
            project_cfg=project_cfg,
            config_data=config_data,
            args=args,
            child_configs=child_configs,
        )

        self.results_title = f"{self.name.upper()} CDC Results"
