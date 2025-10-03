# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test config loading."""

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from hamcrest import assert_that, calling, equal_to, raises

from dvsim.config.load import (
    ConflictingConfigValueError,
    _extract_config_paths,
    _merge_cfg_map,
    _resolve_cfg_path,
    load_cfg,
)

CFG_BASE = Path(__file__).parent / "example_cfgs"


class TestConfigLoader:
    """Test load_cfg."""

    @staticmethod
    @pytest.mark.parametrize(
        ("cfg_path", "exception", "match"),
        [
            # file doesn't exist
            (CFG_BASE / "file_does_not_exist", FileNotFoundError, ""),
            # existing file with no extension
            (CFG_BASE / "config", ValueError, ""),
            # existing file with invalid extension
            (CFG_BASE / "config.invalid", TypeError, ""),
            # empty config file
            (CFG_BASE / "empty.hjson", ValueError, ""),
            # top level config container is list not dict
            (CFG_BASE / "list_on_top.hjson", TypeError, ""),
            (CFG_BASE / "import_cfg_not_list.hjson", TypeError, ".*not a list"),
        ],
    )
    def test_invalid_cfg_raises(
        cfg_path: Path,
        exception: type[Exception],
        match: str,
    ) -> None:
        """Test invalid config raises."""
        assert_that(
            calling(load_cfg).with_args(
                path=cfg_path,
                include_paths=[CFG_BASE],
            ),
            raises(exception, match),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("cfg_path", "expected"),
        [
            (
                Path("basic.hjson"),
                {
                    "name": "basic_config",
                    "a": "b",
                    "b": 3,
                },
            ),
            # With import_cfgs to pull in values from other config files
            (
                Path("with_imports.hjson"),
                {
                    "name": "with_imports",
                    "a": "b",
                    "y": 3,
                    "d": [1, 2, 3],
                    "e": "test",
                },
            ),
            (
                Path("a") / "circular.hjson",
                {
                    "new": "value",
                    "tool": {"sim": {"name": "simulator", "cmd": "sim"}},
                    "name": "with_imports",
                    "d": [1, 2, 3],
                    "e": "test",
                    "a": "b",
                    "y": 3,
                },
            ),
        ],
    )
    def test_load(cfg_path: Path, expected: Mapping) -> None:
        """Test config can be loaded."""
        exp_cfg = dict(expected)
        exp_cfg["self_dir"] = (CFG_BASE / cfg_path).parent

        assert_that(
            load_cfg(path=CFG_BASE / cfg_path, include_paths=[CFG_BASE]),
            equal_to(exp_cfg),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("cfg_path", "selected", "expected"),
        [
            (
                # No selection means load all use configs
                Path("parent.hjson"),
                [],
                {
                    "name": "parent",
                    "d": [1, 2, 3],
                    "e": "test",
                    "cfgs": {
                        CFG_BASE / "child_cfgs" / "child_1.hjson": {
                            "name": "child_1",
                            "test_cases": {
                                "fred": {
                                    "cmd": "test_runner",
                                    "args": ["a", "b", "c"],
                                },
                                "elaine": {
                                    "cmd": "test_runner",
                                    "args": ["g", "h", "i"],
                                },
                            },
                            "a": "b",
                            "y": 3,
                        },
                        CFG_BASE / "child_cfgs" / "child_2.hjson": {
                            "name": "child_2",
                            "test_cases": {
                                "george": {
                                    "cmd": "test_runner",
                                    "args": ["d", "e", "f"],
                                },
                            },
                            "a": "b",
                            "y": 3,
                        },
                    },
                },
            ),
            # TODO: move to an inline config
            # Select all configs explicitly
            (
                Path("parent.hjson"),
                ["child_1", "child_2"],
                {
                    "name": "parent",
                    "d": [1, 2, 3],
                    "e": "test",
                    "cfgs": {
                        CFG_BASE / "child_cfgs" / "child_1.hjson": {
                            "name": "child_1",
                            "test_cases": {
                                "fred": {
                                    "cmd": "test_runner",
                                    "args": ["a", "b", "c"],
                                },
                                "elaine": {
                                    "cmd": "test_runner",
                                    "args": ["g", "h", "i"],
                                },
                            },
                            "a": "b",
                            "y": 3,
                        },
                        CFG_BASE / "child_cfgs" / "child_2.hjson": {
                            "name": "child_2",
                            "test_cases": {
                                "george": {
                                    "cmd": "test_runner",
                                    "args": ["d", "e", "f"],
                                },
                            },
                            "a": "b",
                            "y": 3,
                        },
                    },
                },
            ),
            # Only select the first config
            (
                Path("parent.hjson"),
                ["child_1"],
                {
                    "name": "parent",
                    "d": [1, 2, 3],
                    "e": "test",
                    "cfgs": {
                        CFG_BASE / "child_cfgs" / "child_1.hjson": {
                            "name": "child_1",
                            "test_cases": {
                                "fred": {
                                    "cmd": "test_runner",
                                    "args": ["a", "b", "c"],
                                },
                                "elaine": {
                                    "cmd": "test_runner",
                                    "args": ["g", "h", "i"],
                                },
                            },
                            "a": "b",
                            "y": 3,
                        },
                    },
                },
            ),
            # Only select the second config
            (
                Path("parent.hjson"),
                ["child_2"],
                {
                    "name": "parent",
                    "d": [1, 2, 3],
                    "e": "test",
                    "cfgs": {
                        CFG_BASE / "child_cfgs" / "child_2.hjson": {
                            "name": "child_2",
                            "test_cases": {
                                "george": {
                                    "cmd": "test_runner",
                                    "args": ["d", "e", "f"],
                                },
                            },
                            "a": "b",
                            "y": 3,
                        },
                    },
                },
            ),
        ],
    )
    def test_load_child_use_cfgs(
        cfg_path: Path,
        selected: Sequence[str] | None,
        expected: Mapping,
    ) -> None:
        """Test child configuration files are loaded."""
        cfg = load_cfg(
            path=CFG_BASE / cfg_path,
            include_paths=[CFG_BASE, CFG_BASE / "child_cfgs"],
            select_cfgs=selected,
        )

        # Check the selected config names
        assert_that(
            {c["name"] for c in cfg["cfgs"].values()},
            equal_to({c["name"] for c in expected["cfgs"].values()}),
        )

        # Check the contents of the child configs match expected
        for path in cfg["cfgs"]:
            exp_cfg = expected["cfgs"][path]
            exp_cfg["self_dir"] = path.parent
            assert_that(cfg["cfgs"][path], equal_to(exp_cfg))

        # Double check the entire config matches
        exp_cfg = dict(expected)
        exp_cfg["self_dir"] = (CFG_BASE / cfg_path).parent

        assert_that(cfg, equal_to(exp_cfg))


class TestResolveCfgPath:
    """Test _resolve_cfg_path."""

    @staticmethod
    @pytest.mark.parametrize(
        ("path", "exception"),
        [
            (CFG_BASE / "file_not_exist.hjson", FileNotFoundError),
            (Path("file_not_exist.hjson"), ValueError),
            ("file_not_exist.hjson", ValueError),
            (Path("/absolute/path/that/is/missing.hjson"), FileNotFoundError),
            ("/absolute/path/that/is/missing.hjson", FileNotFoundError),
            ("/path/with/unresolvable_{wildcards}.hjson", KeyError),
        ],
    )
    def test_resolve_cfg_path_invalid_path(
        path: str | Path,
        exception: type[Exception],
    ) -> None:
        """Test that invalid paths raise."""
        assert_that(
            calling(_resolve_cfg_path).with_args(
                path,
                include_paths=(CFG_BASE,),
                wildcard_values={},
            ),
            raises(exception),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("path", "resolved_path", "wildcard_values"),
        [
            # Full path
            (CFG_BASE / "basic.hjson", CFG_BASE / "basic.hjson", {}),
            (str(CFG_BASE / "basic.hjson"), CFG_BASE / "basic.hjson", {}),
            (
                "{cfg_base}/basic.hjson",
                CFG_BASE / "basic.hjson",
                {"cfg_base": CFG_BASE},
            ),
            # Sting path with no wildcards
            (Path("basic.hjson"), CFG_BASE / "basic.hjson", {}),
            ("basic.hjson", CFG_BASE / "basic.hjson", {}),
            ("bas{end}.hjson", CFG_BASE / "basic.hjson", {"end": "ic"}),
            (
                "bas{end}.hj{inner}n",
                CFG_BASE / "basic.hjson",
                {"end": "ic", "inner": "so"},
            ),
            # sub directory
            (
                Path("sub_root") / "other.hjson",
                CFG_BASE / "sub_root" / "other.hjson",
                {},
            ),
            ("sub_root/other.hjson", CFG_BASE / "sub_root" / "other.hjson", {}),
            # relative to additional include path CFG_BASE/sub_root
            (Path("other.hjson"), CFG_BASE / "sub_root" / "other.hjson", {}),
            ("other.hjson", CFG_BASE / "sub_root" / "other.hjson", {}),
        ],
    )
    def test_resolve_cfg_path(
        path: str | Path,
        resolved_path: Path,
        wildcard_values: dict[str, object],
    ) -> None:
        """Test that valid paths can be resolved."""
        assert_that(
            _resolve_cfg_path(
                path,
                include_paths=(CFG_BASE, CFG_BASE / "sub_root"),
                wildcard_values=wildcard_values,
            ),
            equal_to(resolved_path),
        )

    @staticmethod
    def test_extract_config_import_paths() -> None:
        """Test list of import cfgs is retreaved and then filtered from cfg."""
        assert_that(
            _extract_config_paths(
                data={
                    "import_cfgs": ["a.hjson", "b.hjson", "c.hjson"],
                    "a": 1,
                    "b": 2,
                },
                field="import_cfgs",
                include_paths=[CFG_BASE],
                wildcard_values={},
            ),
            equal_to(
                [
                    CFG_BASE / "a.hjson",
                    CFG_BASE / "b.hjson",
                    CFG_BASE / "c.hjson",
                ],
            ),
        )


class TestMergeCfgValues:
    """Test _merge_cfg_values."""

    @staticmethod
    @pytest.mark.parametrize(
        ("obj", "other", "expected"),
        [
            # Empty configuration
            ({}, {}, {}),
            # int
            ({"a": 1}, {}, {"a": 1}),  # Left single value
            ({}, {"a": 1}, {"a": 1}),  # Right single value
            ({"a": 1}, {"a": 1}, {"a": 1}),  # Same values
            ({"b": 1}, {"a": 2}, {"a": 2, "b": 1}),
            ({"top": {"b": 1}}, {"top": {"a": 2}}, {"top": {"a": 2, "b": 1}}),
            # float
            ({"a": 1.5}, {}, {"a": 1.5}),
            ({}, {"a": 1.5}, {"a": 1.5}),
            ({"a": 1.5}, {"a": 1.5}, {"a": 1.5}),
            (
                {"top": {"b": 1.5}},
                {"top": {"a": 2.4}},
                {"top": {"a": 2.4, "b": 1.5}},
            ),
            # str
            ({"a": "v"}, {}, {"a": "v"}),
            ({}, {"a": "v"}, {"a": "v"}),
            ({"a": "v"}, {"a": "v"}, {"a": "v"}),
            ({"a": "v"}, {"a": ""}, {"a": "v"}),  # empty string ignored
            ({"a": ""}, {"a": "v"}, {"a": "v"}),  # empty string ignored
            (
                {"top": {"b": "v1"}},
                {"top": {"a": "v2"}},
                {"top": {"a": "v2", "b": "v1"}},
            ),
            # Lists
            ({"a": []}, {}, {"a": []}),
            ({"a": [1]}, {}, {"a": [1]}),
            ({"a": [1]}, {"a": [2]}, {"a": [1, 2]}),
            ({}, {"a": []}, {"a": []}),
            ({}, {"a": [1]}, {"a": [1]}),
            # three levels merge
            (
                {"top": {"mid": {"b": 1}}},
                {"top": {"mid": {"a": 2}}},
                {"top": {"mid": {"a": 2, "b": 1}}},
            ),
            (
                {"top": {"mid": {"b": [1, 2]}}},
                {"top": {"mid": {"b": [3]}}},
                {"top": {"mid": {"b": [1, 2, 3]}}},
            ),
        ],
    )
    def test_merge_cfg_maps_valid_with_no_conflicts(
        obj: Mapping,
        other: Mapping,
        expected: Mapping,
    ) -> None:
        """Test two configs are merged when no conflicts."""
        assert_that(
            _merge_cfg_map(obj=obj, other=other),
            equal_to(expected),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("obj", "other"),
        [
            # top level conflicts
            ({"a": 1}, {"a": 2}),
            ({"a": "abc"}, {"a": "efg"}),
            # second level conflicts
            ({"top": {"a": 1}}, {"top": {"a": 2}}),
            # third level conflicts
            ({"top": {"mid": {"a": 1}}}, {"top": {"mid": {"a": 2}}}),
        ],
    )
    def test_conflicting_values_raises(
        obj: Mapping,
        other: Mapping,
    ) -> None:
        """Test config maps with conflicting values raises."""
        assert_that(
            calling(_merge_cfg_map).with_args(obj=obj, other=other),
            raises(ConflictingConfigValueError),
        )
