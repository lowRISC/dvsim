# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for tests that are expected to fail (the xfail key)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from dvsim.job.data import (
    CompletedJobStatus,
    JobStatusInfo,
    WorkspaceConfig,
    is_xfail,
    is_xpass,
)
from dvsim.job.status import JobStatus
from dvsim.report.data import IPMeta, ToolMeta
from dvsim.scheduler.core import FAILED_DEP, KILLED_RUNNING_SIGINT
from dvsim.sim import data, flow
from dvsim.sim.flow import SimCfg
from dvsim.sim.report import HtmlReportRenderer, MarkdownReportRenderer
from dvsim.sim_results import BucketedFailures, SimResults
from dvsim.test import Test as DvsimTest
from dvsim.testplan import Result
from dvsim.testplan import Testplan as DvsimTestplan

__all__ = ()

REASON = "needs feature X (issue #1)"
BLOCK = IPMeta(
    name="blk", commit="c0ffee", commit_short="c0f", branch="main", url=None, revision_info=None
)


def _status(
    name: str,
    status: JobStatus,
    *,
    xfail: str | None = None,
    message: JobStatusInfo | str | None = "Error: it broke",
    seed: int = 1,
) -> CompletedJobStatus:
    if isinstance(message, str):
        message = JobStatusInfo(message=message, lines=[3], context=["Error: it broke"])
    return CompletedJobStatus(
        name=name,
        job_type="RunTest",
        seed=seed,
        block=BLOCK,
        tool=ToolMeta(name="vcs", version=""),
        workspace_cfg=WorkspaceConfig(
            timestamp="t",
            project_root=Path("/proj"),
            scratch_root=Path("/scratch"),
            scratch_path=Path("/scratch/blk"),
        ),
        full_name=f"blk:{seed}.{name}",
        qual_name=f"{seed}.{name}",
        target="run",
        log_path=Path(f"/scratch/blk/{name}.log"),
        job_runtime=1.0,
        simulated_time=2.0,
        status=status,
        fail_msg=None if status == JobStatus.PASSED else message,
        xfail=xfail,
    )


class TestXfailKey:
    """The xfail key on a test."""

    def test_default(self) -> None:
        assert DvsimTest({"name": "t"}).xfail == ""

    def test_reason(self) -> None:
        assert DvsimTest({"name": "t", "xfail": REASON}).xfail == REASON

    def test_not_a_string(self) -> None:
        with pytest.raises(SystemExit):
            DvsimTest({"name": "t", "xfail": True})

    def test_merge_two_files(self) -> None:
        """A test defined in two files gets the xfail of the one that sets it."""
        test = DvsimTest({"name": "t", "run_opts": ["+a"]})
        test.merge_mode(DvsimTest({"name": "t", "xfail": REASON}))
        assert test.xfail == REASON


class TestClassify:
    """Which runs count as XFAIL and XPASS."""

    @pytest.mark.parametrize(
        ("status", "xfail", "message", "expected"),
        [
            (JobStatus.FAILED, REASON, "Error: it broke", (True, False)),
            # A killed run is a failure, not the expected one: a timeout (a hang may hide the
            # known failure) or a job that couldn't be launched.
            (JobStatus.KILLED, REASON, "Job timed out after 1 minutes", (False, False)),
            (JobStatus.KILLED, REASON, "Failed to launch job: no such file", (False, False)),
            (JobStatus.KILLED, REASON, None, (False, False)),
            # A run that never ran, or was stopped by a signal, hasn't failed.
            (JobStatus.KILLED, REASON, FAILED_DEP, (False, False)),
            (JobStatus.FAILED, REASON, FAILED_DEP, (False, False)),
            (JobStatus.KILLED, REASON, KILLED_RUNNING_SIGINT, (False, False)),
            (JobStatus.PASSED, REASON, None, (False, True)),
            (JobStatus.FAILED, None, "Error: it broke", (False, False)),
            (JobStatus.PASSED, None, None, (False, False)),
        ],
    )
    def test_classify(self, status, xfail, message, expected) -> None:
        job = _status("t", status, xfail=xfail, message=message)
        assert (
            is_xfail(job.xfail, job.status, job.fail_msg),
            is_xpass(job.xfail, job.status),
        ) == expected


class TestResults:
    """How XFAIL and XPASS runs are counted and bucketed."""

    @pytest.fixture
    def results(self) -> list[CompletedJobStatus]:
        return [
            _status("ok", JobStatus.PASSED),
            _status("bad", JobStatus.FAILED),
            _status("xf", JobStatus.FAILED, xfail=REASON, seed=1),
            _status("xf", JobStatus.PASSED, xfail=REASON, seed=2),
            _status("xf", JobStatus.KILLED, xfail=REASON, message=FAILED_DEP, seed=3),
        ]

    def test_counts(self, results) -> None:
        rows = {row.name: row for row in SimResults(results).table}
        assert (rows["ok"].passing, rows["ok"].total, rows["ok"].xfail) == (1, 1, None)
        assert (rows["bad"].passing, rows["bad"].total) == (0, 1)
        xf = rows["xf"]
        # Every run counts in total, and none of them in passing.
        assert (xf.passing, xf.xfailed, xf.xpassed, xf.total, xf.xfail) == (0, 1, 1, 3, REASON)

    def test_only_xfail(self) -> None:
        """A test whose runs are all XFAIL ran, and has a pass rate of 0."""
        row = SimResults([_status("xf", JobStatus.FAILED, xfail=REASON)]).table[0]
        assert (row.passing, row.total, row.xfailed) == (0, 1, 1)

    def test_unexpected_buckets(self, results) -> None:
        """Real failures, cancelled runs and XPASS are failures; XFAIL isn't."""
        buckets = BucketedFailures.from_job_status(results).buckets
        names = {b: [j.qual_name for j in jobs] for b, jobs in buckets.items()}
        assert names == {
            "Error: it broke": ["1.bad"],
            f"Passed, but expected to fail: {REASON}": ["2.xf"],
            FAILED_DEP.message: ["3.xf"],
        }

    def test_expected_buckets(self, results) -> None:
        buckets = BucketedFailures.from_job_status(results, expected=True).buckets
        assert {b: [j.qual_name for j in jobs] for b, jobs in buckets.items()} == {
            "Error: it broke": ["1.xf"],
        }
        assert buckets["Error: it broke"][0].line == 3


class TestTestplanProgress:
    """A test whose runs are all XFAIL is written, but not passing."""

    def test_progress(self, tmp_path: Path) -> None:
        plan = tmp_path / "plan.hjson"
        plan.write_text(
            '{name: "blk", testpoints: [{name: "tp", desc: "d", stage: "V1", '
            'tests: ["ok", "xf", "missing"]}]}'
        )
        testplan = DvsimTestplan(str(plan), repo_top=tmp_path, name="blk")
        xf = Result("xf", passing=0, total=2)
        xf.xfail, xf.xfailed = REASON, 2
        testplan.map_test_results([Result("ok", passing=1, total=1), xf])
        progress = testplan.progress["V1"]
        assert (progress["total"], progress["written"], progress["passing"]) == (3, 2, 1)


class TestExitCode:
    """XFAIL runs don't make the run fail; XPASS runs do."""

    @staticmethod
    def _has_errors(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, results: list[CompletedJobStatus]
    ) -> bool:
        """Run the real _gen_json_results on a cfg with just the attributes it reads."""
        monkeypatch.setattr(flow, "query_tool_version", lambda _tool: "1")
        plan = tmp_path / "plan.hjson"
        plan.write_text(
            '{name: "blk", testpoints: [{name: "tp", desc: "d", stage: "V1", tests: ["ok", "xf"]}]}'
        )
        cfg = object.__new__(SimCfg)
        cfg.__dict__.update(
            name="blk",
            variant=None,
            commit="c0ffee",
            commit_short="c0f",
            dirty=False,
            branch="main",
            revision=None,
            tool="vcs",
            timestamp="20261025_000000",
            run_only=False,
            build_seed=None,
            testplan=DvsimTestplan(str(plan), repo_top=tmp_path, name="blk"),
            testplan_doc_path=None,
            rel_path="hw/blk/dv/blk_sim_cfg.hjson",
            book=None,
            proj_root=str(tmp_path),
            map_full_testplan=False,
            cov_report_deploy=None,
            cov_report_page=None,
            scratch_path=str(tmp_path),
            cfg_extensions={},
            errors_seen=False,
        )
        cfg._gen_json_results(results, url="")
        return cfg.has_errors()

    def test_xfail_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        results = [
            _status("ok", JobStatus.PASSED),
            _status("xf", JobStatus.FAILED, xfail=REASON),
        ]
        assert not self._has_errors(tmp_path, monkeypatch, results)

    def test_xpass_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        results = [_status("xf", JobStatus.PASSED, xfail=REASON)]
        assert self._has_errors(tmp_path, monkeypatch, results)


def _flow_results(results: list[CompletedJobStatus]) -> data.SimFlowResults:
    """Build flow results with one unmapped testpoint, as _gen_json_results does."""
    tests = {
        row.name: data.TestResult(
            max_time=row.job_runtime,
            sim_time=row.simulated_time,
            passed=row.passing,
            total=row.total,
            percent=100.0 * row.passing / (row.total or 1),
            xfailed=row.xfailed,
            xpassed=row.xpassed,
            xfail=row.xfail,
        )
        for row in SimResults(results).table
    }
    counts = {
        "passed": sum(t.passed for t in tests.values()),
        "total": sum(t.total for t in tests.values()),
        "percent": 50.0,
        "xfailed": sum(t.xfailed for t in tests.values()),
        "xpassed": sum(t.xpassed for t in tests.values()),
    }
    stage = data.TestStage(testpoints={"Unmapped": data.Testpoint(tests=tests, **counts)}, **counts)
    return data.SimFlowResults(
        block=BLOCK,
        tool=ToolMeta(name="vcs", version="1"),
        timestamp=datetime(2026, 10, 25, tzinfo=timezone.utc),
        build_seed=None,
        testplan_ref=None,
        stages={"unmapped": stage},
        coverage=None,
        cov_report_page=None,
        vplan_report_page=None,
        failed_jobs=BucketedFailures.from_job_status(results),
        xfailed_jobs=BucketedFailures.from_job_status(results, expected=True),
        **counts,
    )


class TestReports:
    """XFAIL and XPASS in the reports."""

    def test_markdown_block(self) -> None:
        flow = _flow_results(
            [
                _status("ok", JobStatus.PASSED),
                _status("xf", JobStatus.FAILED, xfail=REASON, seed=1),
                _status("xp", JobStatus.PASSED, xfail=REASON, seed=2),
            ]
        )
        md = MarkdownReportRenderer(None).render_block(flow)["report.md"]
        assert "XFail" in md
        assert "1 (1 XPASS)" in md
        assert "## Failure Buckets" in md
        assert f"Passed, but expected to fail: {REASON}" in md
        assert "## Expected Failures" in md
        assert "has 1 expected failure:" in md

    def test_markdown_no_xfail(self) -> None:
        """Flows without xfail tests look as before."""
        flow = _flow_results([_status("ok", JobStatus.PASSED), _status("bad", JobStatus.FAILED)])
        md = MarkdownReportRenderer(None).render_block(flow)["report.md"]
        assert "XFail" not in md
        assert "Expected Failures" not in md

    def test_markdown_only_xfail(self) -> None:
        """A flow whose runs are all XFAIL shows its table, with a pass rate of 0."""
        flow = _flow_results([_status("xf", JobStatus.FAILED, xfail=REASON)])
        md = MarkdownReportRenderer(None).render_block(flow)["report.md"]
        assert "No results to display." not in md
        assert "0.00 %" in md
        assert "## Expected Failures" in md

    def test_markdown_summary(self) -> None:
        flows = {
            "blk": _flow_results([_status("xf", JobStatus.FAILED, xfail=REASON)]),
            "other": _flow_results([_status("ok", JobStatus.PASSED)]),
        }
        summary = data.SimResultsSummary(
            top=None,
            version=None,
            timestamp=datetime(2026, 10, 25, tzinfo=timezone.utc),
            build_seed=None,
            flow_results={k: v.summary() for k, v in flows.items()},
            report_path=Path("/scratch/reports"),
        )
        md = MarkdownReportRenderer(None).render_summary(summary)["report.md"]
        header = md.strip().splitlines()[0]
        assert header.rstrip("| ").endswith("XFail")

    def test_html_block(self) -> None:
        flow = _flow_results(
            [_status("ok", JobStatus.PASSED), _status("xf", JobStatus.FAILED, xfail=REASON)]
        )
        summary = data.SimResultsSummary(
            top=None,
            version=None,
            timestamp=datetime(2026, 10, 25, tzinfo=timezone.utc),
            build_seed=None,
            flow_results={"blk": flow.summary()},
            report_path=Path("/scratch/reports"),
        )
        html = HtmlReportRenderer().render(summary, {"blk": flow})
        block = html["blk.html"]
        assert "Expected Failures" in block
        assert f'title="{REASON}"' in block
        assert ", 1 xfail" in block
        assert "1 xfail" in html["index.html"]


def _keys(obj: object) -> set[str]:
    """Every key in a JSON value, at any depth."""
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


class TestResultsJson:
    """The xfail keys are in the JSON only when a flow has xfail tests."""

    XFAIL_KEYS = frozenset({"xfailed", "xpassed", "xfail", "xfailed_jobs"})

    def test_without_xfail(self) -> None:
        flow = _flow_results([_status("ok", JobStatus.PASSED), _status("bad", JobStatus.FAILED)])
        dumped = flow.model_dump(mode="json")
        assert not _keys(dumped) & self.XFAIL_KEYS
        assert not _keys(flow.summary().model_dump(mode="json")) & self.XFAIL_KEYS
        assert data.SimFlowResults.model_validate(dumped) == flow

    def test_with_xfail(self) -> None:
        flow = _flow_results(
            [_status("ok", JobStatus.PASSED), _status("xf", JobStatus.FAILED, xfail=REASON)]
        )
        dumped = flow.model_dump(mode="json")
        assert _keys(dumped) >= {"xfailed", "xfail", "xfailed_jobs"}
        assert dumped["xfailed"] == 1
        assert data.SimFlowResults.model_validate(dumped) == flow
