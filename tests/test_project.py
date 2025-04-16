# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test project meta functions."""

from collections.abc import Mapping
from pathlib import Path

import pytest
from hamcrest import assert_that, equal_to

from dvsim.project import Project

__all__ = ()


@pytest.mark.parametrize(
    "data",
    [
        {
            "top_cfg_path": Path("cfg_path.hjson"),
            "root_path": Path("root_path"),
            "src_path": Path("src_path"),
            "branch": "branch",
            "job_prefix": "job_prefix",
            "logfile": Path("logfile"),
        },
    ],
)
def test_project_meta(data: Mapping, tmp_path: Path) -> None:
    """Test Project saving and loading."""
    meta = Project(
        **data,
        scratch_path=tmp_path,
        run_dir=tmp_path / data["branch"],
    )

    meta.save()

    loaded_meta = Project.load(path=meta.run_dir)

    assert_that(loaded_meta, equal_to(meta))
