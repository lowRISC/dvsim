# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the EDA tool utilities."""

import pytest
from hamcrest import assert_that, equal_to, instance_of, none

from dvsim.logging import log
from dvsim.sim.tool.base import SimTool, VersionQuery
from dvsim.tool.utils import _SUPPORTED_SIM_TOOLS, get_sim_tool_plugin, query_tool_version

__all__ = ("TestEDAToolPlugins", "TestToolVersionQuery")

# Representative output captured from the real tools' version-query commands.
_VCS_ID_OUTPUT = """\
vcs script version : X-2025.06
machine name = dab
machine type = linux64
machine os = Linux 6.18.39
The FLEXlm host ID of this machine is "1a2b3c4d5e6f 7g8h9i0j1k2l"
Compiler version = VCS X-2025.06-SP2-1_Full64
VCS Build Date = Jan 29 2026 20:22:37
"""

_XRUN_VERSION_OUTPUT = "TOOL:   xrun(64)        24.03-s007\n"


class TestEDAToolPlugins:
    """Test the EDA tool plug-ins."""

    @staticmethod
    @pytest.mark.parametrize("tool", _SUPPORTED_SIM_TOOLS.keys())
    def test_get_sim_tool_plugin(tool: str) -> None:
        """Test that sim plugins can be retrieved correctly."""
        assert_that(
            get_sim_tool_plugin(tool),
            equal_to(_SUPPORTED_SIM_TOOLS[tool]),
        )

    @staticmethod
    @pytest.mark.parametrize("tool", _SUPPORTED_SIM_TOOLS.keys())
    def test_plugins_implement_simtool_protocol(tool: str) -> None:
        """Test that all sim plugins implement the SimTool interface."""
        plugin = get_sim_tool_plugin(tool)

        assert_that(plugin, instance_of(SimTool))

    @staticmethod
    @pytest.mark.parametrize("tool", _SUPPORTED_SIM_TOOLS.keys())
    def test_plugins_declare_version_query(tool: str) -> None:
        """Test that every plugin declares a version query (inherited or not)."""
        assert_that(get_sim_tool_plugin(tool).version_query, instance_of(VersionQuery))


class TestToolVersionQuery:
    """Test parsing of tool versions from version-query command output."""

    @staticmethod
    @pytest.mark.parametrize(
        ("tool", "output", "expected"),
        [
            ("vcs", _VCS_ID_OUTPUT, "X-2025.06-SP2-1_Full64"),
            ("z01x", _VCS_ID_OUTPUT, "X-2025.06-SP2-1_Full64"),
            ("xcelium", _XRUN_VERSION_OUTPUT, "24.03-s007"),
        ],
    )
    def test_parses_version(tool: str, output: str, expected: str) -> None:
        """Test that the version is parsed from representative tool output."""
        assert_that(query_tool_version(tool, run=lambda _cmd: output), equal_to(expected))

    @staticmethod
    def test_returns_none_when_command_fails() -> None:
        """Test that a failed query (runner returns None) yields None."""
        assert_that(query_tool_version("vcs", run=lambda _cmd: None), none())

    @staticmethod
    def test_returns_none_when_output_unrecognised() -> None:
        """Test that unparseable output yields None rather than a bad version."""
        assert_that(query_tool_version("vcs", run=lambda _cmd: "totally unexpected"), none())

    @staticmethod
    def test_returns_none_when_pattern_lacks_capture_group(monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a groupless pattern is logged and reported as unknown, not raised.

        A missing capture group is a plugin-authoring bug, but querying the version must
        never break a run, so it must be swallowed here rather than escaping as an error.
        """

        class _GrouplessPlugin:
            # `pattern` matches the output but has no group to extract the version from.
            version_query = VersionQuery(cmd="dummy --version", pattern="version")

        monkeypatch.setattr("dvsim.tool.utils.get_sim_tool_plugin", lambda _tool: _GrouplessPlugin)
        errors: list[tuple[object, ...]] = []
        monkeypatch.setattr(log, "error", lambda *args, **_kwargs: errors.append(args))

        result = query_tool_version("vcs", run=lambda _cmd: "version 1.2.3")

        assert_that(result, none())
        assert_that(len(errors), equal_to(1))
        assert_that(errors[0][1], equal_to("vcs"))

    @staticmethod
    def test_returns_none_when_match_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a capture of an empty/whitespace version yields None, not ''.

        This upholds the contract that a truthy version string is returned or None,
        so callers never have to treat "" as a distinct, meaningless version.
        """

        class _EmptyMatchPlugin:
            # The group matches, but captures no non-whitespace version token.
            version_query = VersionQuery(cmd="dummy --version", pattern=r"version:\s*(\S*)")

        monkeypatch.setattr("dvsim.tool.utils.get_sim_tool_plugin", lambda _tool: _EmptyMatchPlugin)

        assert_that(query_tool_version("vcs", run=lambda _cmd: "version: \n"), none())
