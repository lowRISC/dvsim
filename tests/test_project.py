# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test project meta functions."""

from collections.abc import Mapping
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to, instance_of

from dvsim.project import FlowConfig, Project, TopFlowConfig

__all__ = ()


@pytest.mark.parametrize(
    ("data", "flow_config_cls"),
    [
        (
            {
                "top_cfg_path": Path("cfg_path.hjson"),
                "root_path": Path("root_path"),
                "src_path": Path("src_path"),
                "branch": "branch",
                "job_prefix": "job_prefix",
                "logfile": Path("logfile"),
                "config": {
                    "flow": "flow",
                    "name": "name",
                },
            },
            FlowConfig,
        ),
    ],
)
def test_project_config(
    data: Mapping,
    flow_config_cls: type[FlowConfig | TopFlowConfig],
    tmp_path: Path,
) -> None:
    """Test Project saving and loading."""
    meta = Project(
        **data,
        scratch_path=tmp_path,
        run_dir=tmp_path / data["branch"],
    )

    meta.save()

    loaded_meta = Project.load(path=meta.run_dir)

    assert_that(loaded_meta, equal_to(meta))
    assert_that(loaded_meta.config, instance_of(flow_config_cls))
