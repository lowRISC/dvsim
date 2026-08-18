# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the tool-neutral evidence file written for vPlan back-annotation.

The format is a contract with dvplan and with any other flow that consumes it, so these cover
what the file says as much as how it is built: which job statuses map onto which outcome, and that a
run the scheduler cancelled is still reported rather than dropped.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from hamcrest import assert_that, contains_string, equal_to, has_key, is_, none, not_

from dvsim.job.data import JobSpec, JobStatusInfo, WorkspaceConfig
from dvsim.job.status import JobStatus
from dvsim.report.data import IPMeta, ToolMeta
from dvsim.report.dv_evidence import (
    SCHEMA_ID,
    Outcome,
    RunEvidenceCollector,
    run_outcome,
    write_evidence,
)
from dvsim.scheduler.core import (
    ALL_FAILED_DEP,
    FAILED_DEP,
    KILLED_QUEUED,
    KILLED_RUNNING_SIGTERM,
    KILLED_SCHEDULED,
    OnJobCompletionCb,
)
from dvsim.sim.flow import SimCfg

_BLOCK = IPMeta(
    name="hmac",
    variant=None,
    commit="abc123",
    commit_short="abc",
    branch="main",
    url="https://github.com/lowRISC/mocha/tree/abc123",
    revision_info=None,
)
_TOOL = "xcelium"
_WORKSPACE = WorkspaceConfig(
    timestamp="20260813_060029",
    project_root=Path("/proj"),
    scratch_root=Path("/scratch"),
    scratch_path=Path("/scratch/hmac"),
)


def _spec(
    name: str,
    *,
    seed: int | None = 0,
    target: str = "run",
) -> JobSpec:
    """Build the job spec the scheduler hands an observer when a job completes."""
    return JobSpec(
        name=name,
        job_type="RunTest",
        target=target,
        backend=None,
        resources=None,
        seed=seed,
        full_name=f"hmac:{seed}.{name}",
        qual_name=f"{seed}.{name}",
        block=_BLOCK,
        tool=ToolMeta(name=_TOOL, version="unknown"),
        workspace_cfg=_WORKSPACE,
        dependencies=[],
        needs_all_dependencies_passing=True,
        weight=1,
        timeout_mins=None,
        cmd="make run",
        exports={},
        dry_run=False,
        interactive=False,
        odir=f"/scratch/hmac/{seed}.{name}",
        renew_odir=True,
        log_path=Path(f"/scratch/hmac/{seed}.{name}/run.log"),
        pre_launch=lambda: None,
        post_finish=lambda _s: None,
        pass_patterns=[],
        fail_patterns=[],
    )


def _collect(*records: tuple[JobSpec, JobStatus, JobStatusInfo | None]) -> RunEvidenceCollector:
    """Feed a collector the way the scheduler's completion hook does."""
    collector = RunEvidenceCollector()
    for spec, status, reason in records:
        collector.record(spec, status, reason)
    return collector


def _evidence(*records: tuple[JobSpec, JobStatus, JobStatusInfo | None]):
    """Build the evidence document for a set of completed jobs."""
    return _collect(*records).evidence(block=_BLOCK, tool=_TOOL, timestamp="2026-08-13T06:00:29Z")


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    [
        (JobStatus.PASSED, None, Outcome.PASSED),
        (JobStatus.FAILED, JobStatusInfo(message="UVM_ERROR"), Outcome.FAILED),
        # Killed while executing is a different answer from never having started.
        (JobStatus.KILLED, KILLED_RUNNING_SIGTERM, Outcome.KILLED),
        (JobStatus.KILLED, None, Outcome.KILLED),
        (JobStatus.KILLED, FAILED_DEP, Outcome.NOT_RUN),
        (JobStatus.KILLED, ALL_FAILED_DEP, Outcome.NOT_RUN),
        (JobStatus.KILLED, KILLED_SCHEDULED, Outcome.NOT_RUN),
        (JobStatus.KILLED, KILLED_QUEUED, Outcome.NOT_RUN),
    ],
    ids=[
        "passed",
        "failed",
        "killed_running",
        "killed_no_reason",
        "dep_failed",
        "all_deps_failed",
        "dep_killed",
        "killed_queued",
    ],
)
def test_job_status_maps_onto_the_neutral_vocabulary(
    status: JobStatus, reason: JobStatusInfo | None, expected: Outcome
) -> None:
    """`JobStatus.KILLED` covers two outcomes, and the scheduler's reason separates them.

    The cancel reasons are imported from `scheduler.core` rather than restated, so rewording one
    of them fails here instead of silently reclassifying every cancelled run as `killed`.
    """
    assert_that(run_outcome(status, reason), is_(expected))


def test_a_cancelled_run_is_reported_rather_than_dropped() -> None:
    """A run the scheduler cancelled is a hole in the plan, so it has to appear as `not_run`.

    Dropping it would leave the test looking like it passed everything it attempted, when the
    plan expected a run that never happened.
    """
    evidence = _evidence(
        (_spec("hmac_smoke", seed=0), JobStatus.PASSED, None),
        (_spec("hmac_smoke", seed=1), JobStatus.KILLED, FAILED_DEP),
    )

    statuses = [run.status for run in evidence.testcase["hmac_smoke"]]
    assert_that(statuses, equal_to([Outcome.PASSED, Outcome.NOT_RUN]))


def test_runs_are_grouped_by_test_name() -> None:
    """Reseeds of one test share a name, which is what a vPlan addresses them by."""
    evidence = _evidence(
        (_spec("hmac_smoke", seed=0), JobStatus.PASSED, None),
        (_spec("hmac_smoke", seed=1), JobStatus.PASSED, None),
        (_spec("hmac_stress", seed=2), JobStatus.PASSED, None),
    )

    assert_that(sorted(evidence.testcase), equal_to(["hmac_smoke", "hmac_stress"]))
    assert_that(len(evidence.testcase["hmac_smoke"]), equal_to(2))
    assert_that([run.seed for run in evidence.testcase["hmac_smoke"]], equal_to([0, 1]))


def test_only_run_jobs_are_tests() -> None:
    """Builds and coverage jobs share the result stream and are not tests.

    They carry names of their own, so including them would invent testcase items a vPlan could
    never have asked for.
    """
    evidence = _evidence(
        (_spec("hmac_smoke", target="run"), JobStatus.PASSED, None),
        (_spec("default", target="build"), JobStatus.PASSED, None),
        (_spec("cov_merge", target="cov_merge"), JobStatus.PASSED, None),
    )

    assert_that(list(evidence.testcase), equal_to(["hmac_smoke"]))


def test_a_failing_run_records_what_reproduces_and_explains_it() -> None:
    """A failing run carries the seed, the log and the failure somebody needs to read."""
    reason = JobStatusInfo(message="UVM_ERROR digest mismatch", lines=[481])
    evidence = _evidence((_spec("hmac_smoke", seed=7), JobStatus.FAILED, reason))

    run = evidence.testcase["hmac_smoke"][0]
    assert_that(run.status, is_(Outcome.FAILED))
    assert_that(run.seed, equal_to(7))
    assert_that(run.log, equal_to(Path("/scratch/hmac/7.hmac_smoke/run.log")))
    assert_that(run.message, equal_to("UVM_ERROR digest mismatch"))
    assert_that(run.line, equal_to(481))


def test_a_passing_run_records_no_failure() -> None:
    """Failure detail is only meaningful for a run that did not pass."""
    evidence = _evidence((_spec("hmac_smoke"), JobStatus.PASSED, JobStatusInfo(message="ignored")))

    assert_that(evidence.testcase["hmac_smoke"][0].message, is_(none()))


def test_written_results_name_their_schema_and_provenance(tmp_path: Path) -> None:
    """The file says what it is and where it came from, which is what makes it auditable later."""
    evidence = _evidence(
        (_spec("hmac_smoke", seed=0), JobStatus.PASSED, None),
        (_spec("hmac_smoke", seed=1), JobStatus.FAILED, JobStatusInfo(message="boom")),
    )

    path = write_evidence(tmp_path / "reports" / "dv_evidence.json", evidence)
    written = json.loads(path.read_text(encoding="utf-8"))

    assert_that(written["schema"], equal_to(SCHEMA_ID))
    assert_that(written["dut"], equal_to("hmac"))
    assert_that(written["tool"], equal_to(_TOOL))
    assert_that(written["produced_by"], contains_string("dvsim"))
    assert_that(written["testcase"], has_key("hmac_smoke"))
    # A test maps straight to its runs, with no wrapper object in between.
    statuses = [run["status"] for run in written["testcase"]["hmac_smoke"]]
    assert_that(statuses, equal_to(["passed", "failed"]))


def test_the_written_provenance_records_a_dirty_tree(tmp_path: Path) -> None:
    """A vPlan figure produced from uncommitted work must not read as coming from the commit.

    dvsim's own report marks the revision '(dirty)', so an evidence file that dropped the flag
    would disagree with the report for the same run, and the disagreement would only show up
    when somebody went back to reproduce the figure.
    """
    collector = _collect((_spec("hmac_smoke"), JobStatus.PASSED, None))
    clean = write_evidence(tmp_path / "clean.json", collector.evidence(block=_BLOCK, tool=_TOOL))
    dirty = write_evidence(
        tmp_path / "dirty.json",
        collector.evidence(block=_BLOCK.model_copy(update={"dirty": True}), tool=_TOOL),
    )

    # Same block either way, so only the flag can account for the difference.
    assert_that(
        json.loads(clean.read_text(encoding="utf-8"))["revision"], not_(contains_string("dirty"))
    )
    assert_that(
        json.loads(dirty.read_text(encoding="utf-8"))["revision"], contains_string("(dirty)")
    )


def test_the_collector_is_reachable_from_the_scheduler_hook() -> None:
    """The collector's method has to match the callback the scheduler will call it through.

    Wiring it up is the one part unit tests would otherwise miss entirely: a signature drift
    here surfaces only at the end of a real regression, when the vPlan job reads an empty file.
    """
    collector = RunEvidenceCollector()
    scheduler_cb: OnJobCompletionCb = collector.record

    scheduler_cb(_spec("hmac_smoke", seed=3), JobStatus.PASSED, None)

    assert_that(collector.evidence(block=_BLOCK).testcase, has_key("hmac_smoke"))


def test_a_flow_hands_the_scheduler_its_collector() -> None:
    """`SimCfg.job_completion_callback` is what the scheduler is given, so it has to be the sink.

    Called unbound against a stand-in, since constructing a real `SimCfg` needs a whole hjson cfg
    and none of it bears on which observer the flow hands over.
    """
    flow = SimpleNamespace(variant_name="hmac", run_evidence=RunEvidenceCollector())
    flow.cfgs = [flow]

    SimCfg.job_completion_callback(flow)(_spec("hmac_smoke", seed=3), JobStatus.PASSED, None)

    assert_that(flow.run_evidence.evidence(block=_BLOCK).testcase, has_key("hmac_smoke"))
