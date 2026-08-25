# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the FuseSoC integration."""

import logging
from argparse import Namespace
from pathlib import Path

import pytest

from dvsim.config import CONFIG_BASENAME, load_config_file
from dvsim.fusesoc import (
    FuseSoCOptions,
    MappingSpec,
    options_from_config,
    resolve_options,
    rewrite_fusesoc_opts,
)

GENERIC = "lowrisc:prim_generic:all:0.1"
MY_TECH = "lowrisc:prim_my_tech:all:0.1"
TOP = "lowrisc:systems:top_earlgrey:0.1"

# The lint flow's build_opts, as OpenTitan writes them: note that several list
# entries hold more than one token.
LINT_OPTS = [
    "--cores-root /proj/hw",
    "run",
    "--target=lint",
    "--tool=veriblelint",
    "--work-root=/scratch/fusesoc-work",
    f"--mapping={GENERIC}",
    f"--mapping={TOP}",
    "lowrisc:ip:uart",
]


class TestMappingSpec:
    def test_bare_value_appends(self):
        assert MappingSpec.parse(MY_TECH) == MappingSpec(None, MY_TECH)

    def test_old_equals_new_replaces(self):
        assert MappingSpec.parse(f"{GENERIC}={MY_TECH}") == MappingSpec(GENERIC, MY_TECH)

    @pytest.mark.parametrize("value", ["", "  ", f"={MY_TECH}", f"{GENERIC}="])
    def test_rejects_malformed(self, value):
        with pytest.raises(ValueError):
            MappingSpec.parse(value)


class TestRewrite:
    def test_no_options_is_identity(self):
        assert rewrite_fusesoc_opts(LINT_OPTS, FuseSoCOptions()) == LINT_OPTS

    def test_replaces_only_the_named_mapping(self):
        opts = FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),))
        result = rewrite_fusesoc_opts(LINT_OPTS, opts)

        assert f"--mapping={MY_TECH}" in result
        assert f"--mapping={GENERIC}" not in result
        # The top mapping selects the top's constants and must survive.
        assert f"--mapping={TOP}" in result

    def test_replaces_two_token_spelling(self):
        result = rewrite_fusesoc_opts(
            ["run", "--mapping", GENERIC, "core"],
            FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),)),
        )
        assert result == ["run", "--mapping", MY_TECH, "core"]

    def test_bare_mapping_is_appended_after_run(self):
        result = rewrite_fusesoc_opts(
            LINT_OPTS,
            FuseSoCOptions(mappings=(MappingSpec(None, MY_TECH),)),
        )
        assert result[result.index("run") + 1] == f"--mapping={MY_TECH}"
        # The pre-existing mappings are untouched.
        assert f"--mapping={GENERIC}" in result

    def test_cores_root_goes_before_run(self):
        result = rewrite_fusesoc_opts(
            LINT_OPTS,
            FuseSoCOptions(extra_cores_roots=("/elsewhere/prim_my_tech",)),
        )
        run_index = result.index("run")
        assert result[run_index - 2 : run_index] == ["--cores-root", "/elsewhere/prim_my_tech"]
        # The project's own cores-root is kept.
        assert "/proj/hw" in result

    def test_multi_token_entries_are_split(self):
        result = rewrite_fusesoc_opts(LINT_OPTS, FuseSoCOptions(extra_cores_roots=("/x",)))
        assert "--cores-root /proj/hw" not in result
        assert result.count("--cores-root") == 2

    def test_without_run_the_list_is_untouched(self):
        opts = ["--version"]
        result = rewrite_fusesoc_opts(opts, FuseSoCOptions(extra_cores_roots=("/x",)))
        assert result == opts

    def test_unmatched_replacement_warns_and_keeps_list(self):
        opts = FuseSoCOptions(mappings=(MappingSpec("lowrisc:nope:all:0.1", MY_TECH),))
        result = rewrite_fusesoc_opts(LINT_OPTS, opts)
        assert f"--mapping={GENERIC}" in result
        assert MY_TECH not in " ".join(result)


class TestFuseSoCSection:
    def _write(self, path: Path, body: str) -> Path:
        path.write_text(body)
        return path

    def test_relative_cores_root_resolves_against_config_file(self, tmp_path):
        cfg = self._write(
            tmp_path / CONFIG_BASENAME,
            '{fusesoc: {mapping: ["%s=%s"], extra_cores_root: ["prim_my_tech"]}}'
            % (GENERIC, MY_TECH),
        )
        options = options_from_config(load_config_file(cfg), cfg)

        assert options.mappings == (MappingSpec(GENERIC, MY_TECH),)
        assert options.extra_cores_roots == (str(tmp_path / "prim_my_tech"),)

    def test_absolute_cores_root_is_left_alone(self, tmp_path):
        cfg = self._write(
            tmp_path / CONFIG_BASENAME,
            '{fusesoc: {extra_cores_root: ["/abs/path"]}}',
        )
        assert options_from_config(load_config_file(cfg), cfg).extra_cores_roots == ("/abs/path",)

    def test_string_value_is_accepted_as_a_singleton(self, tmp_path):
        cfg = self._write(tmp_path / CONFIG_BASENAME, '{fusesoc: {mapping: "%s"}}' % MY_TECH)
        assert options_from_config(load_config_file(cfg), cfg).mappings == (
            MappingSpec(None, MY_TECH),
        )

    def test_unknown_key_is_rejected(self, tmp_path):
        cfg = self._write(tmp_path / CONFIG_BASENAME, "{fusesoc: {mappings: []}}")
        with pytest.raises(RuntimeError, match="unknown key"):
            options_from_config(load_config_file(cfg), cfg)

    def test_missing_section_is_empty(self, tmp_path):
        cfg = self._write(tmp_path / CONFIG_BASENAME, "{}")
        assert not options_from_config(load_config_file(cfg), cfg)


class TestResolveOptions:
    def test_config_then_cli(self, tmp_path):
        (tmp_path / CONFIG_BASENAME).write_text(
            '{fusesoc: {mapping: ["%s=%s"], extra_cores_root: ["/from/file"]}}'
            % (GENERIC, MY_TECH),
        )
        args = Namespace(
            fusesoc_mapping=["lowrisc:other:all:0.1"],
            fusesoc_extra_cores_root=["/from/cli"],
        )
        cfg = tmp_path / CONFIG_BASENAME
        options = resolve_options(args, load_config_file(cfg), cfg)

        assert options.mappings == (
            MappingSpec(GENERIC, MY_TECH),
            MappingSpec(None, "lowrisc:other:all:0.1"),
        )
        assert options.extra_cores_roots == ("/from/file", "/from/cli")


class TestExpandIntegration:
    """The rewrite must happen inside FlowCfg._expand().

    OneShotCfg._expand() calls super()._expand() and then _create_objects(),
    and the build modes created there take a copy of build_opts. Rewriting
    after _expand() returns would therefore be silently ignored by the flow
    that actually runs FuseSoC, even though the cfg attribute looked right.
    """

    def _make_cfg(self, **attrs: object):
        from dvsim.flow.base import FlowCfg

        class _DummyCfg(FlowCfg):
            def _purge(self) -> None: ...
            def _print_list(self) -> None: ...
            def _create_deploy_objects(self) -> None: ...
            def gen_results(self, results) -> None: ...

        cfg = object.__new__(_DummyCfg)
        cfg.__dict__.update(
            args=Namespace(dump_script=None, resolved_fusesoc_options=None),
            is_primary_cfg=False,
            ignored_wildcards=[],
            build_cmd="",
            build_opts=[],
            flow_cfg_file="/stub/cfg.hjson",
            sv_flist_gen_cmd="",
            sv_flist_gen_opts=[],
        )
        cfg.__dict__.update(attrs)
        return cfg

    def test_expand_rewrites_build_opts(self):
        options = FuseSoCOptions(
            mappings=(MappingSpec(GENERIC, MY_TECH),),
            extra_cores_roots=("/elsewhere",),
        )
        cfg = self._make_cfg(
            args=Namespace(dump_script=None, resolved_fusesoc_options=options),
            # As OpenTitan's common_lint_cfg.hjson spells it.
            build_cmd=" fusesoc",
            build_opts=list(LINT_OPTS),
        )

        cfg._expand()

        assert f"--mapping={MY_TECH}" in cfg.build_opts
        assert f"--mapping={GENERIC}" not in cfg.build_opts
        assert "/elsewhere" in cfg.build_opts

    def test_expand_rewrites_sv_flist_gen_opts(self):
        options = FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),))
        cfg = self._make_cfg(
            args=Namespace(dump_script=None, resolved_fusesoc_options=options),
            sv_flist_gen_cmd="fusesoc",
            sv_flist_gen_opts=["run", f"--mapping={GENERIC}", "--setup core"],
        )

        cfg._expand()

        assert f"--mapping={MY_TECH}" in cfg.sv_flist_gen_opts

    def test_non_fusesoc_commands_are_left_alone(self):
        options = FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),))
        cfg = self._make_cfg(
            args=Namespace(dump_script=None, resolved_fusesoc_options=options),
            build_cmd="make",
            build_opts=list(LINT_OPTS),
        )

        cfg._expand()

        assert cfg.build_opts == LINT_OPTS

    def test_without_options_nothing_changes(self):
        cfg = self._make_cfg(build_cmd=" fusesoc", build_opts=list(LINT_OPTS))

        cfg._expand()

        assert cfg.build_opts == LINT_OPTS


class TestDeduplication:
    """Config files append to these lists, so duplicates arise naturally.

    hw/dv/tools/dvsim/common_sim_cfg.hjson supplies the prim mapping, and a
    chip-level cfg importing it appends its own. Replacing every occurrence of
    the old mapping would then emit the new one twice, and FuseSoC rejects that
    with "The following sources are in multiple mappings".
    """

    def test_replacing_a_repeated_mapping_yields_one(self):
        opts = [
            "run",
            f"--mapping={GENERIC}",
            f"--mapping={TOP}",
            f"--mapping={GENERIC}",
            "core",
        ]
        result = rewrite_fusesoc_opts(
            opts,
            FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),)),
        )

        assert result.count(f"--mapping={MY_TECH}") == 1
        assert result.count(f"--mapping={TOP}") == 1
        assert result == ["run", f"--mapping={MY_TECH}", f"--mapping={TOP}", "core"]

    def test_appending_a_mapping_that_is_already_present(self):
        opts = ["run", f"--mapping={MY_TECH}", "core"]
        result = rewrite_fusesoc_opts(
            opts,
            FuseSoCOptions(mappings=(MappingSpec(None, MY_TECH),)),
        )

        assert result.count(f"--mapping={MY_TECH}") == 1

    def test_two_token_duplicates_are_dropped_whole(self):
        opts = ["run", "--mapping", GENERIC, "--mapping", GENERIC, "core"]
        result = rewrite_fusesoc_opts(
            opts,
            FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),)),
        )

        assert result == ["run", "--mapping", MY_TECH, "core"]


@pytest.fixture
def dvsim_log(caplog):
    """Capture dvsim's own logger, which deliberately does not propagate."""
    logger = logging.getLogger("dvsim")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="dvsim")
    yield caplog
    logger.removeHandler(caplog.handler)


class TestOverrideLogging:
    """Every substitution is logged at INFO.

    These options come from outside the project, so an unlogged one is a change
    to the build that leaves no trace in the tree.
    """

    CONTEXT = "uart_lint build_opts [/proj/hw/ip/uart/dv/uart_sim_cfg.hjson]"

    def test_replacement_is_logged_with_both_vlnvs(self, dvsim_log):
        rewrite_fusesoc_opts(
            LINT_OPTS,
            FuseSoCOptions(mappings=(MappingSpec(GENERIC, MY_TECH),)),
            self.CONTEXT,
        )

        assert [
            m for m in dvsim_log.messages if GENERIC in m and MY_TECH in m and self.CONTEXT in m
        ]

    def test_added_mapping_and_cores_root_are_logged(self, dvsim_log):
        rewrite_fusesoc_opts(
            LINT_OPTS,
            FuseSoCOptions(
                mappings=(MappingSpec(None, MY_TECH),),
                extra_cores_roots=("/elsewhere",),
            ),
            self.CONTEXT,
        )

        assert [m for m in dvsim_log.messages if "--mapping added" in m and MY_TECH in m]
        assert [m for m in dvsim_log.messages if "--cores-root added" in m and "/elsewhere" in m]

    def test_nothing_is_logged_when_nothing_changes(self, dvsim_log):
        rewrite_fusesoc_opts(LINT_OPTS, FuseSoCOptions(), self.CONTEXT)

        assert not [m for m in dvsim_log.messages if "FuseSoC" in m]
