# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the resources that build modes, run modes and tests ask for."""

from types import SimpleNamespace

import pytest

from dvsim.modes import BuildMode, RunMode, check_resources, merge_resources
from dvsim.regression import Regression
from dvsim.test import Test as DvsimTest

__all__ = ()


class TestCheck:
    """Checking and normalising the resources that a mode asks for."""

    def test_names_are_upper_cased(self) -> None:
        assert check_resources({"vipLic": 2}, "x") == {"VIPLIC": 2}

    def test_names_that_differ_in_case_are_one_resource(self) -> None:
        assert check_resources({"lic": 1, "LIC": 2}, "x") == {"LIC": 2}

    @pytest.mark.parametrize(
        "value",
        [["A"], {"A": 0}, {"A": -1}, {"A": "1"}, {"A": True}, {"": 1}, {"A=1": 1}, {"A B": 1}],
    )
    def test_rejects_bad_values(self, value: object) -> None:
        with pytest.raises(SystemExit):
            check_resources(value, "x")

    def test_modes_check_theirs(self) -> None:
        assert BuildMode({"name": "b", "build_resources": {"lic": 1}}).build_resources == {"LIC": 1}
        with pytest.raises(SystemExit):
            RunMode({"name": "r", "run_resources": {"lic": 0}})

    def test_default_is_none_needed(self) -> None:
        assert BuildMode({"name": "b"}).build_resources == {}
        assert DvsimTest({"name": "t"}).run_resources == {}


class TestMerge:
    """Merging the resources of two requests or two modes."""

    def test_larger_count_wins(self) -> None:
        assert merge_resources({"A": 1, "B": 3}, {"B": 2, "C": 1}) == {"A": 1, "B": 3, "C": 1}

    def test_none_is_empty(self) -> None:
        assert merge_resources(None, {"A": 1}) == {"A": 1}
        assert merge_resources({"A": 1}, None) == {"A": 1}

    def test_does_not_modify_its_arguments(self) -> None:
        first = {"A": 1}
        merge_resources(first, {"A": 2})
        assert first == {"A": 1}

    def test_same_mode_in_two_files(self) -> None:
        """Two definitions of one mode merge their resources."""
        (mode,) = [
            m
            for m in BuildMode.create_modes(
                [
                    {"name": "b", "build_resources": {"A": 1}},
                    {"name": "b", "build_resources": {"A": 2, "B": 1}},
                ]
            )
            if m.name == "b"
        ]
        assert mode.build_resources == {"A": 2, "B": 1}

    def test_sub_modes(self) -> None:
        """A build mode gets the build_resources of the build modes it enables."""
        modes = BuildMode.create_modes(
            [
                {"name": "lic", "build_resources": {"A": 1}},
                {"name": "b", "en_build_modes": ["lic"]},
            ]
        )
        (mode,) = [m for m in modes if m.name == "b"]
        assert mode.build_resources == {"A": 1}

    def test_sub_modes_run_resources(self) -> None:
        """A build mode gets the run_resources of the build modes it enables."""
        modes = BuildMode.create_modes(
            [
                {"name": "lic", "run_resources": {"a": 1}},
                {"name": "b", "en_build_modes": ["lic"], "run_resources": {"B": 2}},
            ]
        )
        (mode,) = [m for m in modes if m.name == "b"]
        assert (mode.build_resources, mode.run_resources) == ({}, {"A": 1, "B": 2})


class TestTests:
    """The resources that a test's runs need."""

    def test_build_mode_and_run_modes(self) -> None:
        """A test needs its own run_resources, its run modes' and its build mode's.

        The build mode's build_resources are for its build only.
        """
        build_modes = BuildMode.create_modes(
            [
                {"name": "plain", "build_resources": {"BUILD": 1}},
                {"name": "vip", "build_resources": {"BUILD": 1}, "run_resources": {"VIP": 1}},
            ]
        )
        run_modes = RunMode.create_modes([{"name": "slow", "run_resources": {"SLOT": 2}}])
        sim_cfg = SimpleNamespace(
            build_modes=build_modes,
            run_modes=run_modes,
            en_run_modes=[],
        )

        tests = DvsimTest.create_tests(
            [
                {"name": "t_plain", "build_mode": "plain"},
                {"name": "t_vip", "build_mode": "vip", "en_run_modes": ["slow"]},
                {"name": "t_own", "build_mode": "vip", "run_resources": {"vip": 1, "x": 1}},
            ],
            sim_cfg,
        )

        assert {t.name: t.run_resources for t in tests} == {
            "t_plain": {},
            "t_vip": {"VIP": 1, "SLOT": 2},
            "t_own": {"VIP": 1, "X": 1},
        }


def _sim_cfg(**kwargs: object) -> SimpleNamespace:
    """A sim cfg with one build mode and one run mode that each ask for a resource."""
    build_modes = BuildMode.create_modes(
        [
            {"name": "default"},
            {
                "name": "vip",
                "is_sim_mode": 1,
                "build_resources": {"BUILD_LIC": 1},
                "run_resources": {"RUN_LIC": 1},
            },
        ]
    )
    run_modes = RunMode.create_modes([{"name": "slow", "run_resources": {"SLOT": 2}}])
    cfg = SimpleNamespace(
        build_modes=build_modes, run_modes=run_modes, en_build_modes=[], en_run_modes=[]
    )
    cfg.__dict__.update(kwargs)
    cfg.tests = DvsimTest.create_tests([{"name": "t", "build_mode": "default"}], cfg)
    return cfg


class TestEnabledForTheRun:
    """Modes enabled for a whole run or regression pass their resources on, as they do opts."""

    def test_global_modes(self) -> None:
        cfg = _sim_cfg(en_run_modes=["slow"])
        DvsimTest.merge_global_opts(
            cfg.tests, *[[]] * 9, {"BUILD_LIC": 1}, {"RUN_LIC": 1, "SLOT": 2}
        )
        (test,) = cfg.tests
        assert test.build_mode.build_resources == {"BUILD_LIC": 1}
        assert test.run_resources == {"RUN_LIC": 1, "SLOT": 2}

    def test_global_run_mode_also_enabled_by_the_test(self) -> None:
        """A test skips a run mode that is enabled globally; the global one still counts."""
        build_modes = BuildMode.create_modes([{"name": "default"}])
        run_modes = RunMode.create_modes([{"name": "slow", "run_resources": {"SLOT": 2}}])
        cfg = SimpleNamespace(build_modes=build_modes, run_modes=run_modes, en_run_modes=["slow"])
        tests = DvsimTest.create_tests(
            [{"name": "t", "build_mode": "default", "en_run_modes": ["slow"]}], cfg
        )
        DvsimTest.merge_global_opts(tests, *[[]] * 9, {}, {"SLOT": 2})
        assert tests[0].run_resources == {"SLOT": 2}

    def test_regression_modes(self) -> None:
        cfg = _sim_cfg()
        (regr,) = Regression.create_regressions(
            [{"name": "r", "en_sim_modes": ["vip"], "en_run_modes": ["slow"]}], cfg, cfg.tests
        )
        regr.merge_regression_opts()
        (test,) = regr.tests
        assert test.build_mode.build_resources == {"BUILD_LIC": 1}
        assert test.run_resources == {"RUN_LIC": 1, "SLOT": 2}

    def test_regression_skips_modes_enabled_globally(self) -> None:
        """As for opts, a mode enabled for the run is not added again by a regression."""
        cfg = _sim_cfg(en_build_modes=["vip"], en_run_modes=["slow"])
        (regr,) = Regression.create_regressions(
            [{"name": "r", "en_sim_modes": ["vip"], "en_run_modes": ["slow"]}], cfg, cfg.tests
        )
        assert (regr.build_resources, regr.run_resources) == ({}, {})

    def test_regressions_cannot_set_them_directly(self) -> None:
        with pytest.raises(SystemExit):
            Regression({"name": "r", "run_resources": {"A": 1}})
