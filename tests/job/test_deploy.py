# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test Job deployment models."""

from collections.abc import Mapping

import pytest
from hamcrest import assert_that, equal_to

from dvsim.job.deploy import CompileSim

__all__ = ()


class FakeCliArgs:
    """Fake CLI args."""

    def __init__(self) -> None:
        """Initialise fake command line arguments."""
        self.build_timeout_mins = None
        self.timestamp = "timestamp"


class FakeSimCfg:
    """Fake sim configuration."""

    def __init__(self) -> None:
        """Initialise fake sim configuration."""
        self.name = "flow_name"
        self.variant = "variant"

        self.args = FakeCliArgs()
        self.dry_run = True
        self.gui = False

        self.scratch_path = "/scratch_path"
        self.scratch_root = "/scratch_root"
        self.proj_root = "/project"

        self.exports = []

        self.flow_makefile = "path/to/makefile"
        self.build_cmd = "path/to/{build_mode}/build_cmd"
        self.pre_build_cmds = ["A", "B"]
        self.post_build_cmds = ["C", "D"]
        self.build_dir = "build/dir"
        self.build_pass_patterns = None
        self.build_fail_patterns = None
        self.build_seed = 123

        self.sv_flist_gen_cmd = "gen_cmd"
        self.sv_flist_gen_opts = []
        self.sv_flist_gen_dir = "path/to/gen"

        self.cov = True
        self.cov_db_dir = "path"


class FakeBuildMode:
    """Fake BuildMode."""

    def __init__(self) -> None:
        """Initialise fake BuildMode."""
        self.name = "build_name"
        self.build_timeout_mins = 500
        self.build_mode = "build_mode"
        self.build_opts = ["-b path/here", '-a "Quoted"']


def _build_compile_sim(
    *,
    build_overrides: Mapping | None = None,
    sim_overrides: Mapping | None = None,
    cli_args_overrides: Mapping | None = None,
) -> CompileSim:
    """Build CompileSim object.

    Test helper that takes overrides to apply on top of the default values for
    the BuildMode and SimCfg fake objects.
    """
    cli_args = FakeCliArgs()
    if cli_args_overrides:
        for arg, value in cli_args_overrides.items():
            setattr(cli_args, arg, value)

    build_mode_obj = FakeBuildMode()
    if build_overrides:
        for arg, value in build_overrides.items():
            setattr(build_mode_obj, arg, value)

    sim_cfg = FakeSimCfg()
    if sim_overrides:
        for arg, value in sim_overrides.items():
            setattr(sim_cfg, arg, value)

    # Override the cli args in the sim configuration
    sim_cfg.args = cli_args

    return CompileSim.new(
        build_mode_obj=build_mode_obj,
        sim_cfg=sim_cfg,
    )


class TestCompileSim:
    """Test CompileSim."""

    @staticmethod
    @pytest.mark.parametrize(
        ("build_overrides", "sim_overrides", "exp_cmd"),
        [
            (
                {"dry_run": True},
                {},
                "make -f path/to/makefile build "
                "-n "
                "build_cmd=path/to/build_name/build_cmd "
                "build_dir=build/dir "
                "build_opts='-b path/here -a \"Quoted\"' "
                "post_build_cmds='C && D' "
                "pre_build_cmds='A && B' "
                "proj_root=/project "
                "sv_flist_gen_cmd=gen_cmd "
                "sv_flist_gen_dir=path/to/gen "
                "sv_flist_gen_opts=''",
            ),
            (
                {"dry_run": False},
                {},
                "make -f path/to/makefile build "
                "build_cmd=path/to/build_name/build_cmd "
                "build_dir=build/dir "
                "build_opts='-b path/here -a \"Quoted\"' "
                "post_build_cmds='C && D' "
                "pre_build_cmds='A && B' "
                "proj_root=/project "
                "sv_flist_gen_cmd=gen_cmd "
                "sv_flist_gen_dir=path/to/gen "
                "sv_flist_gen_opts=''",
            ),
        ],
    )
    def test_cmd(build_overrides: Mapping, sim_overrides: Mapping, exp_cmd: str) -> None:
        """Test that a CompileSim has the expected cmd."""
        job = _build_compile_sim(
            build_overrides=build_overrides,
            sim_overrides=sim_overrides,
        )

        assert_that(job.cmd, equal_to(exp_cmd))

    @staticmethod
    @pytest.mark.parametrize(
        ("build_overrides", "sim_overrides", "name", "full_name"),
        [
            ({"name": "fred"}, {"variant": None}, "fred", "flow_name:fred"),
            ({"name": "fred"}, {"variant": "v1"}, "fred", "flow_name_v1:fred"),
            ({"name": "fred"}, {"name": "flow", "variant": None}, "fred", "flow:fred"),
            ({"name": "george"}, {"variant": None}, "george", "flow_name:george"),
            ({"name": "george"}, {"variant": "v2"}, "george", "flow_name_v2:george"),
        ],
    )
    def test_names(
        build_overrides: Mapping,
        sim_overrides: Mapping,
        name: str,
        full_name: str,
    ) -> None:
        """Test that a CompileSim ends up with the expected names."""
        job = _build_compile_sim(
            build_overrides=build_overrides,
            sim_overrides=sim_overrides,
        )

        assert_that(job.name, equal_to(name))
        assert_that(job.qual_name, equal_to(name))
        assert_that(job.full_name, equal_to(full_name))

    @staticmethod
    @pytest.mark.parametrize(
        ("sim_overrides", "seed"),
        [
            ({"build_seed": 123}, 123),
            ({"build_seed": 631}, 631),
        ],
    )
    def test_seed(
        sim_overrides: Mapping,
        seed: int,
    ) -> None:
        """Test that a CompileSim ends up with the expected seed."""
        job = _build_compile_sim(
            sim_overrides=sim_overrides,
        )

        assert_that(job.seed, equal_to(seed))

    @staticmethod
    @pytest.mark.parametrize(
        ("cli_args_overrides", "build_overrides", "timeout"),
        [
            ({"build_timeout_mins": 111}, {}, 111),
            ({}, {"build_timeout_mins": 112}, 112),
        ],
    )
    def test_timeout(
        cli_args_overrides: Mapping,
        build_overrides: Mapping,
        timeout: int,
    ) -> None:
        """Test that a CompileSim ends up with the expected timeout."""
        job = _build_compile_sim(
            build_overrides=build_overrides,
            cli_args_overrides=cli_args_overrides,
        )

        assert_that(job.build_timeout_mins, equal_to(timeout))
