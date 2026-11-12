# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test how reports show the cfg extensions (--cfg-extend) of a flow."""

import json
from datetime import datetime, timezone
from pathlib import Path

from dvsim.report.data import CfgExtensionMeta, GitRevisionMeta, IPMeta, ToolMeta
from dvsim.sim.data import SimFlowResults, SimResultsSummary
from dvsim.sim.report import HtmlReportRenderer, MarkdownReportRenderer
from dvsim.sim_results import BucketedFailures

__all__ = ()

TS = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _results(*extensions: CfgExtensionMeta) -> SimFlowResults:
    return SimFlowResults(
        block=IPMeta(
            name="blk",
            commit="c" * 40,
            commit_short="c" * 7,
            branch="b",
            url=None,
            revision_info=None,
        ),
        tool=ToolMeta(name="vcs", version="1"),
        timestamp=TS,
        build_seed=None,
        testplan_ref=None,
        stages={},
        coverage=None,
        cov_report_page=None,
        vplan_report_page=None,
        failed_jobs=BucketedFailures(buckets={}),
        passed=1,
        total=1,
        percent=100.0,
        extensions=extensions,
    )


def _summary(results: SimFlowResults) -> SimResultsSummary:
    return SimResultsSummary(
        top=None,
        version=None,
        timestamp=TS,
        build_seed=None,
        flow_results={"blk": results.summary()},
        report_path=Path("/reports"),
    )


NO_GIT = CfgExtensionMeta(path="/overlay/ok.hjson")
TRACKED = CfgExtensionMeta(
    path="/overlay/dv/ext.hjson",
    revision=GitRevisionMeta(
        origin="git@example.com:org/overlay.git",
        commit="a" * 40,
        commit_short="aaaaaaa",
        dirty=True,
    ),
)


class TestExtensionsInReports:
    """The extensions and their revisions in the results and reports."""

    def test_summary_keeps_extensions(self) -> None:
        assert _results(TRACKED, NO_GIT).summary().extensions == (TRACKED, NO_GIT)

    def test_json_round_trip(self) -> None:
        results = _results(TRACKED, NO_GIT)
        assert SimFlowResults.model_validate_json(results.model_dump_json()) == results

    def test_json_without_extensions_leaves_out_the_key(self) -> None:
        results = _results()

        assert "extensions" not in json.loads(results.model_dump_json())
        flow = json.loads(_summary(results).model_dump_json())["flow_results"]["blk"]
        assert "extensions" not in flow
        assert SimFlowResults.model_validate_json(results.model_dump_json()) == results

    def test_json_with_extensions_has_the_key(self) -> None:
        results = _results(NO_GIT)

        assert json.loads(results.model_dump_json())["extensions"] == [
            {"path": "/overlay/ok.hjson", "revision": None}
        ]
        flow = json.loads(_summary(results).model_dump_json())["flow_results"]["blk"]
        assert flow["extensions"] == [{"path": "/overlay/ok.hjson", "revision": None}]

    def test_markdown_gives_the_revision(self) -> None:
        block = MarkdownReportRenderer().render_block(_results(TRACKED, NO_GIT))["report.md"]

        assert (
            "### Cfg extensions:\n\n* `/overlay/dv/ext.hjson` (revision `aaaaaaa`, dirty, "
            "from git@example.com:org/overlay.git)\n* `/overlay/ok.hjson`"
        ) in block

    def test_markdown_without_extensions(self) -> None:
        block = MarkdownReportRenderer().render_block(_results())["report.md"]

        assert "Cfg extensions" not in block

    def test_html_gives_the_revision(self) -> None:
        results = _results(TRACKED)

        page = HtmlReportRenderer().render(_summary(results), {"blk": results})["blk.html"]

        assert "Extension: ext.hjson sha: aaaaaaa (dirty)" in page
        assert "git@example.com:org/overlay.git" in page
        assert "a" * 40 in page
