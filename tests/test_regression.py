# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for regressions that include other regressions."""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from dvsim.regression import Regression
from dvsim.test import Test as DvsimTest

TEST_NAMES = ("a", "b", "c", "d")


@dataclass(frozen=True)
class FakeTest:
    """The part of a test that regression resolution reads. Hashable, as tests go in a set."""

    name: str


@pytest.fixture(autouse=True)
def fresh_name_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression and Test record every name they create on the class itself."""
    monkeypatch.setattr(Regression, "item_names", [])
    monkeypatch.setattr(DvsimTest, "item_names", [])


def create(regdicts: list[dict]) -> dict[str, Regression]:
    """Create the regressions of a cfg that defines the tests in TEST_NAMES."""
    tests = [FakeTest(name) for name in TEST_NAMES]
    sim_cfg = SimpleNamespace(tests=tests, en_build_modes=[], en_run_modes=[])
    regrs = Regression.create_regressions(regdicts, sim_cfg, tests)
    return {regr.name: regr for regr in regrs}


def names_of(regr: Regression) -> set[str]:
    """Names of the tests a regression runs."""
    return {test.name for test in regr.tests}


class TestIncludedRegressions:
    def test_runs_the_union_of_the_included_tests(self) -> None:
        """Setting only `regressions` must not fall back to running every test."""
        regrs = create(
            [
                {"name": "regression_a", "tests": ["a", "b"]},
                {"name": "regression_b", "tests": ["c"]},
                {"name": "regression_a_b", "regressions": ["regression_a", "regression_b"]},
            ]
        )

        assert names_of(regrs["regression_a_b"]) == {"a", "b", "c"}
        assert names_of(regrs["regression_a"]) == {"a", "b"}
        assert names_of(regrs["regression_b"]) == {"c"}

    def test_keeps_its_own_tests(self) -> None:
        regrs = create(
            [
                {"name": "regression_a", "tests": ["a", "b"]},
                {"name": "combined", "tests": ["d"], "regressions": ["regression_a"]},
            ]
        )

        assert names_of(regrs["combined"]) == {"a", "b", "d"}

    def test_merges_with_a_declaration_in_another_file(self) -> None:
        """A cfg adds `regressions` to a regression that a common cfg already declares."""
        regrs = create(
            [
                {"name": "combined", "tests": ["a"], "reseed": 1},
                {"name": "regression_b", "tests": ["c"]},
                {"name": "combined", "regressions": ["regression_b"]},
            ]
        )

        assert names_of(regrs["combined"]) == {"a", "c"}
        assert regrs["combined"].reseed == 1

    def test_inclusion_is_transitive(self) -> None:
        regrs = create(
            [
                {"name": "outer", "regressions": ["middle"]},
                {"name": "middle", "tests": ["a"], "regressions": ["inner"]},
                {"name": "inner", "tests": ["d"]},
            ]
        )

        assert names_of(regrs["outer"]) == {"a", "d"}
        assert names_of(regrs["middle"]) == {"a", "d"}

    def test_test_names_keep_order_without_duplicates(self) -> None:
        regrs = create(
            [
                {"name": "first", "tests": ["b", "a"]},
                {"name": "second", "tests": ["a", "c"]},
                {"name": "both", "regressions": ["first", "second"]},
            ]
        )

        assert regrs["both"].test_names == ["b", "a", "c"]

    def test_including_an_all_tests_regression_runs_all_tests(self) -> None:
        regrs = create(
            [
                {"name": "all"},
                {"name": "everything", "tests": ["a"], "regressions": ["all"]},
            ]
        )

        assert names_of(regrs["everything"]) == set(TEST_NAMES)

    def test_options_of_an_included_regression_do_not_apply(self) -> None:
        regrs = create(
            [
                {"name": "regression_b", "tests": ["c"], "run_opts": ["+opt_b=1"]},
                {
                    "name": "combined",
                    "regressions": ["regression_b"],
                    "run_opts": ["+opt_combined=1"],
                },
            ]
        )

        assert regrs["combined"].run_opts == ["+opt_combined=1"]
        assert regrs["regression_b"].run_opts == ["+opt_b=1"]


class TestIncludedRegressionErrors:
    @pytest.mark.parametrize("name", ["missing", "a"])
    def test_including_something_that_is_not_a_regression_exits(self, name: str) -> None:
        with pytest.raises(SystemExit):
            create([{"name": "combined", "regressions": [name]}])

    def test_including_itself_exits(self) -> None:
        with pytest.raises(SystemExit):
            create([{"name": "combined", "regressions": ["combined"]}])

    def test_a_cycle_exits(self) -> None:
        with pytest.raises(SystemExit):
            create(
                [
                    {"name": "x", "tests": ["a"], "regressions": ["y"]},
                    {"name": "y", "regressions": ["x"]},
                ]
            )
