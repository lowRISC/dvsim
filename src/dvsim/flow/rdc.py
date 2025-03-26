# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""RDC Configuration Class."""

from argparse import Namespace
from collections.abc import Mapping, Sequence
from pathlib import Path

from dvsim.flow.lint import LintCfg
from dvsim.project import ProjectMeta


class RdcCfg(LintCfg):
    """Reset Domain Crossing."""

    flow = "rdc"

    def __init__(
        self,
        flow_cfg_file: Path,
        project_cfg: ProjectMeta,
        config_data: Mapping,
        args: Namespace,
        child_configs: Sequence["RdcCfg"] | None = None,
    ) -> None:
        self.waves = args.waves or ""

        super().__init__(
            flow_cfg_file=flow_cfg_file,
            project_cfg=project_cfg,
            config_data=config_data,
            args=args,
            child_configs=child_configs,
        )

        self.results_title = f"{self.name.upper()} RDC Results"
