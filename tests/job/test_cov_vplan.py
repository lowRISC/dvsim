# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the vPlan back-annotation job.

These construct the job for real. Every other test around the vPlan exercises a helper in
isolation, which cannot catch the job failing to build itself: `Deploy.__init__` derives
attributes by name and order, so a missing one is an `AttributeError` at config time that no
amount of testing the command builder would reveal.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from hamcrest import assert_that, contains_string, equal_to, is_, none

from dvsim.job.data import DependencyPolicy, WorkspaceConfig
from dvsim.job.deploy import CovVPlan
from dvsim.job.status import JobStatus
from dvsim.report.vplan import ANNOTATED_HJSON, ANNOTATED_HTML, VPLAN_DIR


def _cfg(**overrides: object) -> SimpleNamespace:
    """Build the smallest sim cfg a `CovVPlan` can be constructed against."""
    attrs: dict[str, object] = {
        "name": "hmac",
        "flow": "sim",
        "variant": "",
        "tool": "xcelium",
        "gui": False,
        "interactive": False,
        "dry_run": False,
        "scratch_path": "/scratch/hmac",
        "commit": "abc123",
        "commit_short": "abc",
        "branch": "main",
        "revision": "",
        "build_mode": "default",
        "exports": [],
        "flow_makefile": "sim.mk",
        "proj_root": "/proj",
        "vplan": "/proj/hw/ip/hmac/data/hmac_vplan.hjson",
        "dut_instance": "tb.dut",
        "dvplan_inspect": "",
        "cov": True,
        "cov_report_dir": "/scratch/hmac/cov_report",
        "cov_vplan_prepare_opts": ["--bypass-trace"],
        "cov_vplan_process_opts": [""],
        "timeout_mins": None,
        "max_odirs": 5,
        "workspace_cfg": WorkspaceConfig(
            timestamp="20260818_090000",
            project_root=Path("/proj"),
            scratch_root=Path("/scratch"),
            scratch_path=Path("/scratch/hmac"),
        ),
    }
    attrs.update(overrides)
    return SimpleNamespace(**attrs)


@pytest.fixture
def job() -> CovVPlan:
    """Construct the job the way the sim flow does."""
    return CovVPlan([], _cfg())


def test_the_job_constructs_and_lands_in_its_own_output_directory(job: CovVPlan) -> None:
    """`Deploy` derives `odir` from an attribute named after the target, inside `_set_attrs`.

    That ordering is easy to get wrong and fails at config time rather than at run time, taking
    the whole invocation down before a single test starts.
    """
    assert_that(job.odir, equal_to(f"/scratch/hmac/{VPLAN_DIR}"))
    assert_that(job.qual_name, equal_to("cov_vplan"))
    assert_that(job.full_name, equal_to("hmac:cov_vplan"))
    assert_that(job.annotated_hjson, equal_to(Path("/scratch/hmac") / VPLAN_DIR / ANNOTATED_HJSON))
    assert_that(job.report_page, equal_to(Path("/scratch/hmac") / VPLAN_DIR / ANNOTATED_HTML))


def test_the_job_builds_a_runnable_command(job: CovVPlan) -> None:
    """The command is built during construction, so a broken builder is a config-time failure."""
    assert_that(job.cmd, contains_string("dvplan prepare_vplan --bypass-trace"))
    assert_that(job.cmd, contains_string("dvplan process_results"))
    assert_that(job.cmd, contains_string("--coverage xcelium_report"))
    assert_that(job.cmd, contains_string("--coverage dv_evidence"))
    # `cov_vplan_process_opts: [""]` is idiomatic hjson for "none" and must not become an
    # empty argument, which argparse would read as the DUT name.
    assert_that(job.cmd, contains_string("-s hmac tb.dut"))


def test_a_run_without_coverage_still_annotates() -> None:
    """Without --cov there is no vendor report, and the plan is scored from the evidence alone."""
    job = CovVPlan([], _cfg(cov=False))

    assert_that(job.cmd, contains_string("--coverage dv_evidence"))
    assert_that("xcelium_report" in job.cmd, is_(False))


def test_an_inspection_pattern_matching_nothing_fails_at_config_time() -> None:
    """The cfg names records that are not there, so the run must stop before it burns a regression.

    The command is built in `Deploy.__init__`, so this lands while the jobs are still being
    created rather than hours later inside dvplan.
    """
    with pytest.raises(ValueError, match="No inspection records matched"):
        CovVPlan([], _cfg(dvplan_inspect="/proj/hw/ip/hmac/dv/inspections/*.json"))


def test_a_failing_run_still_gets_its_plan_scored(job: CovVPlan) -> None:
    """A regression where nothing passed is the case the plan most needs to describe.

    `ANY_PASSING` would not do here. With `--cov` this job has one dependency, the coverage
    report, so anything that stops the report also stops the plan being scored.
    """
    assert_that(job.dependency_policy, equal_to(DependencyPolicy.ALWAYS))


def test_no_score_is_read_back_when_the_job_did_not_pass(job: CovVPlan) -> None:
    """Reading a plan the job failed to write would report a stale or partial figure."""
    job.post_finish()(JobStatus.FAILED)

    assert_that(job.vplan_coverage, is_(none()))
