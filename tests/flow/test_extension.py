# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for cfg extensions (--cfg-extend)."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from dvsim.cli.run import parse_args
from dvsim.flow.base import FlowCfg
from dvsim.flow.extension import CfgExtension, check_cfg_extensions_used
from dvsim.flow.factory import make_cfg

__all__ = ()

# A sim cfg with just enough in it to load. Like a real block cfg, it gets its
# tool options from an imported file, so the test can check that an
# extension's list entries come after those.
CHILD_CFG = """{
  name: blk
  flow: sim
  tool: vcs
  scratch_path: "{scratch_root}/blk"
  import_cfgs: ["{proj_root}/hw/tool.hjson"]
  build_modes: [{name: "waves_off"}, {name: "xprop"}, {name: "build_seed"}]
  tests: [{name: "t1"}]
  regressions: []
  testplan: ""
  blk_var: "orig"
  blk_empty: ""
}"""

TOOL_CFG = '{build_opts: ["-f {proj_root}/sv.f"], run_opts: ["+tool"]}'

PRIMARY_CFG = """{
  name: top
  flow: sim
  scratch_path: "{scratch_root}/top"
  use_cfgs: ["{proj_root}/hw/blk_sim_cfg.hjson"]
}"""


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    """A git repo holding a primary cfg and its one child, "blk"."""
    root = tmp_path.resolve() / "proj"
    (root / "hw").mkdir(parents=True)
    (root / "hw" / "blk_sim_cfg.hjson").write_text(CHILD_CFG)
    (root / "hw" / "tool.hjson").write_text(TOOL_CFG)
    (root / "hw" / "top_sim_cfgs.hjson").write_text(PRIMARY_CFG)
    git = ["git", "-C", str(root)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return root


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _load(proj: Path, cfg: str, *extends: str, argv: Sequence[str] = ()) -> FlowCfg:
    argv = [str(proj / "hw" / cfg), "--scratch-root", str(proj.parent / "scratch"), *argv]
    argv += ["--branch", "b"]
    for ext in extends:
        argv += ["--cfg-extend", ext]
    args = parse_args(argv)
    args.timestamp = args.timestamp_long = "ts"
    return make_cfg(args.cfg, args, str(proj))


def _blk(cfg: FlowCfg) -> FlowCfg:
    (blk,) = [c for c in cfg.cfgs if c.name == "blk"]
    return blk


class TestParse:
    """Parsing NAME=PATH."""

    def test_name_and_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert CfgExtension.parse("blk=ext/x.hjson") == CfgExtension(
            "blk", tmp_path.resolve() / "ext" / "x.hjson"
        )

    def test_symlinks_are_kept(self, tmp_path: Path) -> None:
        """The path is spelt as {file_dir} spells it, through any symlink."""
        (tmp_path / "real").mkdir()
        (tmp_path / "link").symlink_to(tmp_path / "real")

        ext = CfgExtension.parse(f"blk={tmp_path}/link/../link/x.hjson")

        assert ext.path == tmp_path / "link" / "x.hjson"

    @pytest.mark.parametrize("value", ["blk", "=x.hjson", "blk=", " = "])
    def test_rejects_malformed(self, value: str) -> None:
        with pytest.raises(ValueError, match="NAME=PATH"):
            CfgExtension.parse(value)

    def test_cli_rejects_malformed(self, proj: Path) -> None:
        with pytest.raises(SystemExit):
            parse_args([str(proj / "hw" / "top_sim_cfgs.hjson"), "--cfg-extend", "blk"])


class TestMerge:
    """Merging an extension into its cfg."""

    @pytest.mark.parametrize("top", ["top_sim_cfgs.hjson", "blk_sim_cfg.hjson"])
    def test_lists_follow_the_cfgs_own(self, proj: Path, tmp_path: Path, top: str) -> None:
        """The extension reaches the cfg whether it is a child or run alone.

        Its list entries land after everything the cfg imports, so build
        options that need the tool's filelist come after it.
        """
        ext = _write(
            tmp_path / "overlay" / "ext.hjson",
            """{
              build_opts: ["+incdir+/overlay", "/overlay/bind.sv"]
              tests: [{name: "t2"}]
            }""",
        )

        blk = _blk(_load(proj, top, f"blk={ext}"))

        assert blk.build_opts[:3] == [f"-f {proj}/sv.f", "+incdir+/overlay", "/overlay/bind.sv"]
        assert blk.run_opts[:1] == ["+tool"]
        assert [t.name for t in blk.tests] == ["t1", "t2"]
        assert list(blk.cfg_extensions) == [CfgExtension("blk", ext)]

    def test_imports_and_order(self, proj: Path, tmp_path: Path) -> None:
        """Extensions apply in command-line order, each with its own imports."""
        first = _write(
            tmp_path / "a" / "ext.hjson",
            '{import_cfgs: ["{file_dir}/more.hjson"], run_opts: ["+a"]}',
        )
        _write(tmp_path / "a" / "more.hjson", '{run_opts: ["+a_more"]}')
        second = _write(tmp_path / "b" / "ext.hjson", '{run_opts: ["+b"]}')

        blk = _blk(_load(proj, "top_sim_cfgs.hjson", f"blk={first}", f"blk={second}"))

        assert blk.run_opts[:4] == ["+tool", "+a", "+a_more", "+b"]
        assert list(blk.cfg_extensions) == [CfgExtension("blk", first), CfgExtension("blk", second)]

    def test_named_twice_is_an_error(
        self, proj: Path, tmp_path: Path, dvsim_log: pytest.LogCaptureFixture
    ) -> None:
        """The same NAME=PATH twice would merge the extension twice."""
        ext = _write(tmp_path / "ext.hjson", '{run_opts: ["+x"]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={ext}", f"blk={ext}")

        assert f"blk={ext} is given more than once" in dvsim_log.text

    def test_overrides_change_a_scalar(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(
            tmp_path / "ext.hjson",
            '{overrides: [{name: "blk_var", value: "new"}]}',
        )

        blk = _blk(_load(proj, "top_sim_cfgs.hjson", f"blk={ext}"))

        assert blk.blk_var == "new"

    def test_sets_a_scalar_the_cfg_leaves_empty(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", '{blk_empty: "set"}')

        blk = _blk(_load(proj, "top_sim_cfgs.hjson", f"blk={ext}"))

        assert blk.blk_empty == "set"

    @pytest.mark.parametrize(
        ("key", "value"), [("tool", "xcelium"), ("scratch_path", "/elsewhere")]
    )
    def test_conflicting_scalar_is_an_error(
        self, proj: Path, tmp_path: Path, dvsim_log: pytest.LogCaptureFixture, key: str, value: str
    ) -> None:
        ext = _write(tmp_path / "ext.hjson", f'{{{key}: "{value}"}}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={ext}")

        assert f"Cannot extend cfg 'blk' with {ext}: Value for key '{key}'" in dvsim_log.text
        # The reason doesn't repeat the path.
        assert f"'{ext}'" not in dvsim_log.text

    def test_tool_from_the_command_line_wins(self, proj: Path, tmp_path: Path) -> None:
        """As in the cfg's own files, the extension's tool gives way to --tool."""
        ext = _write(tmp_path / "ext.hjson", '{tool: "xcelium"}')

        blk = _blk(_load(proj, "top_sim_cfgs.hjson", f"blk={ext}", argv=["--tool", "vcs"]))

        assert blk.tool == "vcs"

    def test_unresolved_import_is_an_error(
        self, proj: Path, tmp_path: Path, dvsim_log: pytest.LogCaptureFixture
    ) -> None:
        ext = _write(tmp_path / "ext.hjson", '{import_cfgs: ["{nope}/x.hjson"]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={ext}")

        assert "Can't resolve the name of an imported file" in dvsim_log.text

    def test_use_cfgs_is_an_error(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", '{use_cfgs: ["/x.hjson"]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={ext}")

    def test_missing_file_is_an_error(self, proj: Path, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={tmp_path / 'nope.hjson'}")


class TestNames:
    """Matching an extension to a cfg by name."""

    def test_unknown_name_is_an_error(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", '{run_opts: ["+x"]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blkk={ext}")

    def test_name_as_the_cfgs_own_files_give_it(
        self, proj: Path, tmp_path: Path, dvsim_log: pytest.LogCaptureFixture
    ) -> None:
        """An extension matches the name before overrides; one that matched nothing is an error.

        Here the cfg's own overrides rename it from 'blk' to 'blk2' after the extensions merge.
        """
        cfg = proj / "hw" / "blk_sim_cfg.hjson"
        cfg.write_text(
            CHILD_CFG.replace("name: blk", 'name: "{n}"\n  n: blk').replace(
                "testplan:", 'overrides: [{name: "n", value: "blk2"}]\n  testplan:'
            )
        )
        ext = _write(tmp_path / "ext.hjson", '{run_opts: ["+x"]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk2={ext}")
        assert "(loaded: blk)" in dvsim_log.text

        (blk2,) = _load(proj, "top_sim_cfgs.hjson", f"blk={ext}").cfgs
        assert (blk2.name, blk2.run_opts.count("+x")) == ("blk2", 1)

    def test_primary_name_is_an_error(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", '{run_opts: ["+x"]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"top={ext}")

    def test_messages(self) -> None:
        exts = [CfgExtension("a", Path("/a")), CfgExtension("top", Path("/t"))]

        assert check_cfg_extensions_used(exts, exts[:1], ["a", "b"], "top") == [
            (
                "Cfg extension /t names the primary cfg 'top': only a cfg that runs jobs "
                "(a child, or a cfg run on its own) can be extended."
            )
        ]
        assert check_cfg_extensions_used(exts[:1], [], ["b"], None) == [
            "Cfg extension /a names 'a', but no loaded cfg has that name (loaded: b)."
        ]


def _reasons(cfg: FlowCfg) -> list[str]:
    """Why each skipped extension of cfg was skipped."""
    return [meta.skipped for meta in cfg.cfg_extensions.values() if meta.skipped is not None]


def _skipped(cfg: FlowCfg) -> list[CfgExtension]:
    """The extensions of cfg that were skipped."""
    return [ext for ext, meta in cfg.cfg_extensions.items() if meta.skipped is not None]


def _load_skip(proj: Path, *extends: str) -> FlowCfg:
    return _load(proj, "top_sim_cfgs.hjson", *extends, argv=["--on-cfg-extend-error", "skip"])


class TestOnError:
    """--on-cfg-extend-error: a broken extension stops the run, or is skipped."""

    def test_default_is_error(self, proj: Path) -> None:
        assert parse_args([str(proj / "hw" / "top_sim_cfgs.hjson")]).on_cfg_extend_error == "error"

    def test_parse_error_is_skipped(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", "{tests: [{name: ")

        blk = _blk(_load_skip(proj, f"blk={ext}"))

        assert [t.name for t in blk.tests] == ["t1"]
        # It was matched, and skipped.
        assert list(blk.cfg_extensions) == [CfgExtension("blk", ext)]
        (reason,) = _reasons(blk)
        assert "can't be parsed" in reason
        # The reports name the extension beside the reason, so the reason doesn't.
        assert str(ext) not in reason

    def test_parse_error_stops_the_run_by_default(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", "{tests: [{name: ")

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={ext}")

    def test_partial_merge_is_undone(self, proj: Path, tmp_path: Path) -> None:
        """Keys merged before the one that fails are put back as they were."""
        ext = _write(
            tmp_path / "ext.hjson",
            '{run_opts: ["+x"], tests: [{name: "t2"}], new_key: "n", blk_var: "clash"}',
        )

        blk = _blk(_load_skip(proj, f"blk={ext}"))

        assert blk.run_opts == ["+tool"]
        assert [t.name for t in blk.tests] == ["t1"]
        assert not hasattr(blk, "new_key")
        assert blk.blk_var == "orig"
        (reason,) = _reasons(blk)
        assert "conflicting value" in reason
        # The reason doesn't repeat the path, which the skip names already.
        assert str(ext) not in reason

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ('[{name: "no_such_key", value: "x"}]', "which the cfg doesn't have"),
            ('[{name: "blk_var", value: 3}]', "doesn't match the type"),
            ('[{name: "blk_var"}]', "needs a name and a value"),
            ('{name: "blk_var", value: "x"}', "Conflicting types"),
            ('[{name: ["blk_var"], value: "x"}]', "needs a key name"),
        ],
    )
    def test_bad_override_is_skipped(
        self, proj: Path, tmp_path: Path, overrides: str, message: str
    ) -> None:
        ext = _write(tmp_path / "ext.hjson", f'{{run_opts: ["+x"], overrides: {overrides}}}')

        blk = _blk(_load_skip(proj, f"blk={ext}"))

        assert blk.run_opts == ["+tool"]
        assert getattr(blk, "overrides", []) == []
        (reason,) = _reasons(blk)
        assert message in reason

    def test_bad_override_stops_the_run_by_default(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", '{overrides: [{name: "no_such_key", value: "x"}]}')

        with pytest.raises(SystemExit):
            _load(proj, "top_sim_cfgs.hjson", f"blk={ext}")

    def test_override_taken_by_an_earlier_extension(self, proj: Path, tmp_path: Path) -> None:
        first = _write(tmp_path / "a.hjson", '{overrides: [{name: "blk_var", value: "a"}]}')
        second = _write(tmp_path / "b.hjson", '{overrides: [{name: "blk_var", value: "b"}]}')

        blk = _blk(_load_skip(proj, f"blk={first}", f"blk={second}"))

        assert blk.blk_var == "a"
        assert _skipped(blk) == [CfgExtension("blk", second)]
        (reason,) = _reasons(blk)
        assert "already overridden" in reason

    def test_later_extensions_still_apply(self, proj: Path, tmp_path: Path) -> None:
        broken = _write(tmp_path / "a.hjson", '{use_cfgs: ["/x.hjson"]}')
        good = _write(tmp_path / "b.hjson", '{run_opts: ["+b"]}')

        blk = _blk(_load_skip(proj, f"blk={broken}", f"blk={good}"))

        assert blk.run_opts == ["+tool", "+b"]
        # Both in command-line order; only the broken one skipped.
        assert list(blk.cfg_extensions) == [CfgExtension("blk", broken), CfgExtension("blk", good)]
        assert _skipped(blk) == [CfgExtension("blk", broken)]

    def test_missing_file_is_skipped(self, proj: Path, tmp_path: Path) -> None:
        blk = _blk(_load_skip(proj, f"blk={tmp_path / 'nope.hjson'}"))

        (reason,) = _reasons(blk)
        assert "Not a file" in reason

    def test_unresolved_import_is_skipped(self, proj: Path, tmp_path: Path) -> None:
        ext = _write(tmp_path / "ext.hjson", '{import_cfgs: ["{nope}/x.hjson"]}')

        blk = _blk(_load_skip(proj, f"blk={ext}"))

        (reason,) = _reasons(blk)
        assert "Can't resolve the name of an imported file" in reason

    @pytest.mark.parametrize("name", ["blkk", "top"])
    def test_unknown_name_is_skipped(
        self, proj: Path, tmp_path: Path, dvsim_log: pytest.LogCaptureFixture, name: str
    ) -> None:
        """No cfg matched it, so no report shows it: there is only the warning."""
        ext = _write(tmp_path / "ext.hjson", '{run_opts: ["+x"]}')

        blk = _blk(_load_skip(proj, f"{name}={ext}"))

        assert f"Skipping: Cfg extension {ext} names" in dvsim_log.text
        assert not blk.cfg_extensions

        assert blk.run_opts == ["+tool"]


class TestRevision:
    """The git revision of each extension."""

    def test_revision_is_recorded(self, proj: Path, tmp_path: Path) -> None:
        overlay = tmp_path / "overlay"
        ext = _write(overlay / "dv" / "ext.hjson", '{run_opts: ["+x"]}')
        git = ["git", "-C", str(overlay)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "dv"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
        head = subprocess.run(
            [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        outside = _write(tmp_path / "loose" / "ext.hjson", '{run_opts: ["+y"]}')

        blk = _blk(_load(proj, "top_sim_cfgs.hjson", f"blk={ext}", f"blk={outside}"))

        revision = blk.cfg_extensions[CfgExtension("blk", ext)].revision
        assert revision is not None
        assert (revision.commit, revision.dirty) == (head, False)
        assert blk.cfg_extensions[CfgExtension("blk", outside)].revision is None
