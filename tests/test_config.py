# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for dvsim's own config file."""

from pathlib import Path

import pytest

from dvsim.config import (
    CONFIG_BASENAME,
    XDG_SUBPATH,
    check_top_level_keys,
    find_config_file,
    load_config_file,
    proj_root_from_config,
    read_section,
    resolve_path,
)

KNOWN = frozenset({"proj_root", "fusesoc"})


def write(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


class TestDiscovery:
    def test_walks_upwards(self, tmp_path):
        """The config file sits beside the project dvsim is run from inside."""
        cfg = write(tmp_path / CONFIG_BASENAME, "{}")
        nested = tmp_path / "opentitan" / "hw" / "ip"
        nested.mkdir(parents=True)

        assert find_config_file(None, start_dir=nested) == cfg

    def test_nearest_wins(self, tmp_path):
        write(tmp_path / CONFIG_BASENAME, "{}")
        nested = tmp_path / "opentitan"
        nested.mkdir()
        nearer = write(nested / CONFIG_BASENAME, "{}")

        assert find_config_file(None, start_dir=nested) == nearer

    def test_explicit_path_wins(self, tmp_path):
        write(tmp_path / CONFIG_BASENAME, "{}")
        explicit = write(tmp_path / "other.hjson", "{}")

        assert find_config_file(str(explicit), start_dir=tmp_path) == explicit

    def test_missing_explicit_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            find_config_file(str(tmp_path / "absent.hjson"))


class TestLoading:
    def test_parses_a_dict(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, "{fusesoc: {mapping: []}}")

        assert load_config_file(cfg) == {"fusesoc": {"mapping": []}}

    def test_rejects_a_non_dict(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, "[1, 2]")

        with pytest.raises(RuntimeError, match="must contain a dict"):
            load_config_file(cfg)

    def test_rejects_malformed_hjson(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, "{ this is not valid")

        with pytest.raises(RuntimeError, match="Failed to parse"):
            load_config_file(cfg)


class TestReadSection:
    KEYS = frozenset({"mapping"})

    def test_missing_section_is_empty(self, tmp_path):
        assert read_section({}, "fusesoc", self.KEYS, tmp_path) == {}

    def test_unknown_key_is_rejected(self, tmp_path):
        """A typo should fail loudly rather than silently do nothing."""
        with pytest.raises(RuntimeError, match="unknown key"):
            read_section({"fusesoc": {"mappings": []}}, "fusesoc", self.KEYS, tmp_path)

    def test_non_dict_section_is_rejected(self, tmp_path):
        with pytest.raises(RuntimeError, match="must be a dict"):
            read_section({"fusesoc": []}, "fusesoc", self.KEYS, tmp_path)


class TestResolvePath:
    """Relative values are relative to the config file, not the caller."""

    def test_relative_resolves_against_the_base(self, tmp_path):
        assert resolve_path("opentitan", tmp_path) == tmp_path / "opentitan"

    def test_absolute_is_left_alone(self, tmp_path):
        assert resolve_path("/elsewhere/opentitan", tmp_path) == Path("/elsewhere/opentitan")


class TestProjRoot:
    def test_relative_resolves_against_the_config_file(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, '{proj_root: "opentitan"}')

        assert proj_root_from_config(load_config_file(cfg), cfg) == tmp_path / "opentitan"

    def test_absolute_is_left_alone(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, '{proj_root: "/elsewhere/ot"}')

        assert proj_root_from_config(load_config_file(cfg), cfg) == Path("/elsewhere/ot")

    def test_absent_is_none(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, "{}")

        assert proj_root_from_config(load_config_file(cfg), cfg) is None

    def test_non_string_is_rejected(self, tmp_path):
        cfg = write(tmp_path / CONFIG_BASENAME, "{proj_root: 3}")

        with pytest.raises(RuntimeError, match="must be a string"):
            proj_root_from_config(load_config_file(cfg), cfg)


class TestTopLevelKeys:
    def test_known_keys_accepted(self, tmp_path):
        check_top_level_keys({"proj_root": "x", "fusesoc": {}}, KNOWN, tmp_path)

    def test_unknown_key_is_rejected(self, tmp_path):
        """A typo should fail loudly rather than silently do nothing."""
        with pytest.raises(RuntimeError, match="unknown top-level key"):
            check_top_level_keys({"proj_roots": "x"}, KNOWN, tmp_path)


class TestXdgFallback:
    """The per-user file is named like the in-tree one, for consistency."""

    def test_used_when_nothing_is_found_by_walking_up(self, tmp_path, monkeypatch):
        xdg = tmp_path / "xdg"
        cfg = xdg / XDG_SUBPATH
        cfg.parent.mkdir(parents=True)
        write(cfg, "{}")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        empty = tmp_path / "elsewhere"
        empty.mkdir()

        assert find_config_file(None, start_dir=empty) == cfg
        assert cfg.name == CONFIG_BASENAME

    def test_a_nearer_file_wins_over_it(self, tmp_path, monkeypatch):
        xdg = tmp_path / "xdg"
        (xdg / XDG_SUBPATH).parent.mkdir(parents=True)
        write(xdg / XDG_SUBPATH, "{}")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        nearer = write(workspace / CONFIG_BASENAME, "{}")

        assert find_config_file(None, start_dir=workspace) == nearer
