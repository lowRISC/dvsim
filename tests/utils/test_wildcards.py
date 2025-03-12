# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""pytest-based testing for functions in utils.py."""

import os
from collections.abc import Mapping
from pathlib import Path

import pytest
from hamcrest import assert_that, calling, equal_to, raises

from dvsim.utils import (
    find_and_substitute_wildcards,
    subst_wildcards,
)


class TestSubstWildcards:
    """Test subst_wildcards."""

    @staticmethod
    @pytest.mark.parametrize(
        ("input_str", "values", "expected"),
        [
            # Basic checks
            ("foo {x} baz", {"x": "bar"}, "foo bar baz"),
            # Stringify
            (
                "{a}, {b}, {c}, {d}, {e}",
                {
                    "a": "a",
                    "b": True,
                    "c": 42,
                    "d": ["{b}", 10],
                    "e": Path("./path/to/somewhere"),
                },
                "a, 1, 42, 1 10, path/to/somewhere",
            ),
            # Environment variables. We will always have PWD and can probably
            # assume that this won't itself have any braced substrings.
            ("{PWD}", {}, os.environ["PWD"]),
            # Computed variable names (probably not a great idea, but it's
            # probably good to check this works the way we think)
            ("{a}b}", {"a": "a {", "b": "bee"}, "a bee"),
            # Some eval_cmd calls (using echo, which should always work)
            ("{eval_cmd}echo foo {b}", {"b": "bar"}, "foo bar"),
            ("foo {eval_cmd}echo {b}", {"b": "bar"}, "foo bar"),
            # Make sure that nested commands work
            ("{eval_cmd} {eval_cmd} echo echo a", {}, "a"),
            # Recursive expansion
            (
                "{var}",
                {
                    "var": "{{foo}_xyz_{bar}}",
                    "foo": "p",
                    "bar": "q",
                    "p_xyz_q": "baz",
                },
                "baz",
            ),
            # Check we support (non-circular) recursion
            ("{a}", {"a": "{b}", "b": "c"}, "c"),
        ],
    )
    def test_substitutions(
        input_str: str,
        values: dict,
        expected: str,
    ) -> None:
        """Check that wildcards are substituted as expected."""
        assert_that(subst_wildcards(input_str, values), equal_to(expected))

    @staticmethod
    @pytest.mark.parametrize(
        ("input_str", "values", "expected"),
        [
            ("{biggles}", {}, "{biggles}"),
            ("{biggles} {b}", {"b": "bee"}, "{biggles} bee"),
        ],
    )
    def test_substitutions_error_okay(
        input_str: str,
        values: dict,
        expected: str,
    ) -> None:
        """Check missing wildcards are left with ignore_error True."""
        assert_that(
            subst_wildcards(
                var=input_str,
                wildcard_values=values,
                ignore_error=True,
            ),
            equal_to(expected),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("input_str", "values", "ignored", "expected"),
        [
            # With match in mdict
            (
                "{a} {b}",
                {"a": "aye", "b": "bee"},
                ["a"],
                "{a} bee",
            ),
            # Without match in mdict
            (
                "{a} {b}",
                {"b": "bee"},
                ["a"],
                "{a} bee",
            ),
        ],
    )
    def test_substitutions_with_ignored_wildcards(
        *,
        input_str: str,
        values: dict,
        ignored: list,
        expected: str,
    ) -> None:
        """Check that wildcards are substituted as expected."""
        assert_that(
            subst_wildcards(
                var=input_str,
                wildcard_values=values,
                ignored_wildcards=ignored,
                ignore_error=False,
            ),
            equal_to(expected),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("var", "wildcard_values", "ignore_error", "exception", "match"),
        [
            # missing wildcard value
            (
                "{biggles} {b}",
                {"b": "bee"},
                False,
                ValueError,
                "unknown wildcard, '{biggles}'",
            ),
            # wildcard with non string value
            (
                "{a}",
                {"a": object()},
                False,
                ValueError,
                "not of a supported type",
            ),
            # Circular recursion
            (
                "{a}",
                {"a": "{b}", "b": "{a}"},
                False,
                ValueError,
                "circular expansion of wildcard '{a}'",
            ),
            # Circular recursion - even with ignore_error=True
            (
                "{a}",
                {"a": "{b}", "b": "{a}"},
                True,
                ValueError,
                "circular expansion of wildcard '{a}'",
            ),
        ],
    )
    def test_with_errors_raise(
        *,
        var: str,
        wildcard_values: dict,
        ignore_error: bool,
        exception: type[Exception],
        match: str,
    ) -> None:
        """Check error handling."""
        assert_that(
            calling(subst_wildcards).with_args(
                var=var,
                wildcard_values=wildcard_values,
                ignore_error=ignore_error,
            ),
            raises(exception, match),
        )


class TestFindAndSubstituteWildcards:
    """Test find_and_substitute_wildcards."""

    @staticmethod
    @pytest.mark.parametrize(
        ("obj", "wildcards", "expected"),
        [
            # Empty objects
            ((), {}, []),
            ([], {}, []),
            ([(), ()], {}, [[], []]),
            ({"a": ()}, {}, {"a": []}),
            ({"a": {}}, {}, {"a": {}}),
            # unknown objects are left as they are
            (1, {}, 1),
            # String objects can still be passed
            ("foo {x} baz", {"x": "bar"}, "foo bar baz"),
            # list elements are substituted
            (
                ["foo {x} baz", "other {x}"],
                {"x": "bar"},
                ["foo bar baz", "other bar"],
            ),
            (
                ["{x}", ["foo {x} baz"], ["other {x}"]],
                {"x": "bar"},
                ["bar", ["foo bar baz"], ["other bar"]],
            ),
            # map values are substituted
            ({"a": "{x}"}, {"x": "bar"}, {"a": "bar"}),
            (
                {"a": "{x}", "b": {1: "foo {x}", (1, 2): "steel {x}"}},
                {"x": "bar"},
                {"a": "bar", "b": {1: "foo bar", (1, 2): "steel bar"}},
            ),
        ],
    )
    def test_substitutions(
        obj: object,
        wildcards: dict,
        expected: object,
    ) -> None:
        """Check that wildcards are substituted as expected."""
        assert_that(
            find_and_substitute_wildcards(
                obj=obj,
                wildcard_values=wildcards,
            ),
            equal_to(expected),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("obj", "expected"),
        [
            # Empty objects
            ({}, {}),
            ({"a": ()}, {"a": []}),
            ({"a": {}}, {"a": {}}),
            # single level substitutions
            (
                {"a": "foo {x} baz", "x": "bar"},
                {"a": "foo bar baz", "x": "bar"},
            ),
            (
                {"a": "foo {x} baz", "x": "{eval_cmd} echo bar"},
                {"a": "foo bar baz", "x": "bar"},
            ),
            (
                {"a": "foo {x} baz {y}", "x": "bar", "y": 1},
                {"a": "foo bar baz 1", "x": "bar", "y": 1},
            ),
            (
                {"a": "foo {x} baz {y}", "x": "bar {y}", "y": 1},
                {"a": "foo bar 1 baz 1", "x": "bar 1", "y": 1},
            ),
            # Two level substitutions
            (
                {"a": ["foo {x}", "baz {y}"], "x": "bar {y}", "y": 1},
                {"a": ["foo bar 1", "baz 1"], "x": "bar 1", "y": 1},
            ),
        ],
    )
    def test_self_substitution(
        obj: Mapping,
        expected: object,
    ) -> None:
        """Check that a dictionary can be passed as both object and wildcards.

        DVSim config is treated as both the object and the wildcard mapping.
        This causes some confusion in parsing and it might be good to provide
        some clarity in this area. However for the moment this is a required
        feature for compatibility.
        """
        assert_that(
            find_and_substitute_wildcards(
                obj=obj,
                wildcard_values=obj,
            ),
            equal_to(expected),
        )
