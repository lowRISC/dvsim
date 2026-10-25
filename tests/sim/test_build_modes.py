# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for how SimCfg picks the primary build mode of a run."""

import logging
from dataclasses import dataclass, field

import pytest

from dvsim.sim import flow
from dvsim.sim.flow import SimCfg

__all__ = ()


@dataclass(frozen=True)
class FakeBuildMode:
    """A build mode; builds of two modes with the same key are equivalent."""

    name: str
    key: str = field(default="", compare=False)


class FakeCompileSim:
    """Stands in for CompileSim: a build named after its build mode."""

    def __init__(self, build_mode_obj: FakeBuildMode, _sim_cfg: SimCfg) -> None:
        """Make the build of a build mode."""
        self.name = build_mode_obj.name
        self.key = build_mode_obj.key or build_mode_obj.name

    def is_equivalent_job(self, other: "FakeCompileSim") -> bool:
        """Whether two builds are interchangeable."""
        return self.key == other.key


def _deploy(
    monkeypatch: pytest.MonkeyPatch,
    primary: str,
    *modes: FakeBuildMode,
    defined: tuple[str, ...] = (),
    cov: bool = False,
) -> SimCfg:
    """Run _create_deploy_objects for a build-only run of the given modes.

    The SimCfg is made without its constructor, which needs a whole project; only the
    attributes that _create_deploy_objects reads are set. defined names build modes of the
    cfg that the run doesn't build.
    """
    monkeypatch.setattr(flow, "CompileSim", FakeCompileSim)
    cfg = object.__new__(SimCfg)
    cfg.__dict__.update(
        name="blk",
        tool="vcs",
        primary_build_mode=primary,
        build_list=list(modes),
        run_list=[],
        build_modes=[*modes, *map(FakeBuildMode, defined)],
        build_only=True,
        run_only=False,
        gui=False,
        gui_debug=False,
        cov=cov,
    )
    cfg._create_build_and_run_list = lambda: None
    cfg._create_deploy_objects()
    return cfg


class TestPrimaryBuildMode:
    """Picking the primary build mode of a run."""

    def test_kept_when_built(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _deploy(monkeypatch, "default", FakeBuildMode("other"), FakeBuildMode("default"))
        assert cfg.primary_build_mode == "default"

    def test_single_build_becomes_primary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _deploy(monkeypatch, "default", FakeBuildMode("other"))
        assert cfg.primary_build_mode == "other"

    def test_follows_an_equivalent_build(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _deploy(
            monkeypatch,
            "cover",
            FakeBuildMode("plain", key="same"),
            FakeBuildMode("cover", key="same"),
            FakeBuildMode("other"),
        )
        assert cfg.primary_build_mode == "plain"

    def test_falls_back_when_not_built(
        self, monkeypatch: pytest.MonkeyPatch, dvsim_log: pytest.LogCaptureFixture
    ) -> None:
        cfg = _deploy(
            monkeypatch,
            "default",
            FakeBuildMode("zeta"),
            FakeBuildMode("alpha"),
            defined=("default",),
            cov=True,
        )

        assert cfg.primary_build_mode == "alpha"
        assert [b.name for b in cfg.builds] == ["zeta", "alpha"]
        assert any(
            '"primary_build_mode: default"' in r.getMessage() and "Using alpha" in r.getMessage()
            for r in dvsim_log.records
        )

    def test_fallback_without_coverage_does_not_warn(
        self, monkeypatch: pytest.MonkeyPatch, dvsim_log: pytest.LogCaptureFixture
    ) -> None:
        cfg = _deploy(
            monkeypatch,
            "default",
            FakeBuildMode("zeta"),
            FakeBuildMode("alpha"),
            defined=("default",),
        )
        assert cfg.primary_build_mode == "alpha"
        assert not [r for r in dvsim_log.records if r.levelno >= logging.WARNING]

    def test_undefined_primary_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A primary_build_mode that names no build mode is a typo, not a fallback."""
        with pytest.raises(SystemExit):
            _deploy(monkeypatch, "defualt", FakeBuildMode("zeta"), FakeBuildMode("alpha"))

    def test_nothing_to_do_still_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(SystemExit):
            _deploy(monkeypatch, "default")
