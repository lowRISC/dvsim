# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate reports."""

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, TypeAlias

from tabulate import tabulate

from dvsim.logging import log
from dvsim.report.data import IPMeta
from dvsim.sim.data import SimFlowResults, SimResultsSummary
from dvsim.templates.render import render_static, render_template
from dvsim.utils import TS_FORMAT_LONG
from dvsim.utils.fs import relative_to

__all__ = (
    "HtmlReportRenderer",
    "JsonReportRenderer",
    "MarkdownReportRenderer",
    "ReportRenderer",
    "display_report",
    "gen_reports",
    "write_report",
)


def _plural(item: str, n: int | Collection[Any], suffix: str = "s") -> str:
    if not isinstance(n, int):
        n = len(n)
    return item if n == 1 else item + suffix


def _indent_by_levels(lines: Iterable[tuple[int, str]], indent_spaces: int = 4) -> str:
    """Format per-line indentation of (0-indexed level, msg) log messages."""
    return "\n".join(" " * lvl * indent_spaces + msg for lvl, msg in lines)


# Report rendering returns mappings of relative report paths to (string) contents.
ReportArtifacts: TypeAlias = dict[str, str]


class ReportRenderer(Protocol):
    """Renders/formats result reports, returning mappings of relative paths to (string) content."""

    format_name: str

    def render(
        self,
        summary: SimResultsSummary,
        flow_results: Mapping[str, SimFlowResults],
        outdir: Path | None = None,
    ) -> ReportArtifacts:
        """Render a report of the sim flow results into output artifacts."""
        ...


class JsonReportRenderer:
    """Renders/dumps a JSON report of the sim results."""

    format_name = "json"

    def render(
        self,
        summary: SimResultsSummary,
        flow_results: Mapping[str, SimFlowResults],
        outdir: Path | None = None,
    ) -> ReportArtifacts:
        """Render a JSON report of the sim flow results into output artifacts."""
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)

        artifacts = {}

        for results in flow_results.values():
            file_name = results.block.variant_name()
            log.debug("Generating JSON report for '%s'", file_name)
            block_file = f"{file_name}.json"
            artifacts[block_file] = results.model_dump_json()
            if outdir is not None:
                (outdir / block_file).write_text(artifacts[block_file])

        top_log_suffix = "" if summary.top is None else f" for {summary.top.name}"
        log.debug("Generating JSON summary report%s", top_log_suffix)
        artifacts["index.json"] = summary.model_dump_json()
        if outdir is not None:
            (outdir / "index.json").write_text(artifacts["index.json"])

        return artifacts


class HtmlReportRenderer:
    """Renders a HTML report of the sim results."""

    format_name = "html"

    def render(
        self,
        summary: SimResultsSummary,
        flow_results: Mapping[str, SimFlowResults],
        outdir: Path | None = None,
    ) -> ReportArtifacts:
        """Render a HTML report of the sim flow results into output artifacts."""
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)

        artifacts = {}

        # Generate block HTML pages
        for results in flow_results.values():
            file_name = results.block.variant_name()
            log.debug("Generating HTML report for '%s'", file_name)
            block_file = f"{file_name}.html"
            artifacts[block_file] = render_template(
                path="reports/block_report.html",
                data={"results": results, "version": summary.version},
            )
            if outdir is not None:
                (outdir / block_file).write_text(artifacts[block_file])

        # Regardless of whether we have a top or there is only one block, we always generate a
        # summary page for now.
        top_log_suffix = "" if summary.top is None else f" for {summary.top.name}"
        log.debug("Generating HTML summary report%s", top_log_suffix)
        artifacts["index.html"] = render_template(
            path="reports/summary_report.html",
            data={"summary": summary},
        )
        if outdir is not None:
            (outdir / "index.html").write_text(artifacts["index.html"])

        # Generate other static site contents
        artifacts.update(self.render_static_content(outdir))

        return artifacts

    def render_static_content(self, outdir: Path | None = None) -> ReportArtifacts:
        """Render static CSS / JS artifacts for HTML report generation."""
        static_files = [
            "css/style.css",
            "css/bootstrap.min.css",
            "js/bootstrap.bundle.min.js",
            "js/htmx.min.js",
        ]

        artifacts = {}

        for name in static_files:
            artifacts[name] = render_static(path=name)
            if outdir is not None:
                artifact_path = outdir / name
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text(artifacts[name])

        return artifacts


class MarkdownReportRenderer:
    """Renders a Markdown report of the sim results."""

    format_name = "markdown"

    MAX_TESTS_PER_BUCKET = 5
    MAX_RESEEDS_PER_BUCKETED_TEST = 2

    def __init__(self, html_link_base: Path | None = None, relative_to: Path | None = None) -> None:
        """Construct a Markdown report renderer.

        Args:
            html_link_base: The path to the dir that HTML reports are written into, if using HTML
              links. If not provided, no HTML links will be generated in the summary report.
            relative_to: The path that HTML report links should be relative to.

        """
        self.html_link_base = html_link_base
        self.relative_to = relative_to

    def render(
        self,
        summary: SimResultsSummary,
        flow_results: Mapping[str, SimFlowResults],
        outdir: Path | None = None,
    ) -> ReportArtifacts:
        """Render a Markdown report of the sim flow results."""
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)

        report_md = [
            self.render_block(results=flow_result)["report.md"]
            for flow_result in flow_results.values()
        ]
        report_md.append(self.render_summary(summary)["report.md"])

        report = "\n".join(report_md)
        if outdir is not None:
            (outdir / "report.md").write_text(report)

        return {"report.md": report}

    def render_block(self, results: SimFlowResults) -> ReportArtifacts:
        """Render a Markdown report of the sim flow results for a given block/flow."""
        # Generate block result metadata information
        report_md = self.render_metadata(
            results.block,
            results.timestamp,
            results.build_seed,
        )
        testplan_ref = (results.testplan_ref or "").strip()
        if len(results.stages) > 0 and testplan_ref:
            report_md += f"\n### [Testplan]({testplan_ref})"
        report_md += f"\n### Simulator: {results.tool.name.upper()}"

        # Record a summary of the simulation results, coverage, and failure buckets, if applicable.
        result_summary = self.render_block_results(results)
        if result_summary:
            report_md += "\n\n" + result_summary

        return {"report.md": report_md}

    def render_metadata(
        self,
        scope: IPMeta,
        timestamp: datetime,
        seed: int | None,
        title: str = "Simulation Results",
    ) -> str:
        """Generate a Markdown string summary of the result metadata.

        Args:
            scope: The scope (block/top) to generate metadata from.
            timestamp: The timestamp metadata info to include.
            seed: The build seed, if one was used in this run.
            title: The title to use as a suffix (to "NAME %s"). Defaults to "Simulation Results".

        """
        name = scope.variant_name(sep="/")
        report_md = f"## {name.upper()} {title}"
        report_md += f"\n### {timestamp.strftime(TS_FORMAT_LONG)}"

        revision = (scope.revision_info or "").strip()
        if not revision:
            revision = f"Github Revision: [`{scope.commit_short}`]({scope.url})"
        report_md += f"\n### {revision}"
        report_md += f"\n### Branch: {scope.branch}"

        if seed is not None:
            report_md += f"\n### Build randomization enabled with --build-seed {seed}"

        return report_md

    def render_block_results(self, results: SimFlowResults) -> str:
        """Generate a Markdown string covering the results, coverage and failure buckets."""
        report_md = self.render_result_table(results) if results.total else "No results to display."

        # TODO: need to optionally generate a progress table if `--map-full-testplan` was set.
        # This can be passed through and set when instantiating the markdown renderer, but
        # right now we don't record the correct information for testplan progress in the sim
        # results, so we leave this incomplete for now.

        if results.coverage:
            coverage_table = self.render_coverage_table(results)
            if coverage_table:
                report_md += "\n\n" + coverage_table

        if results.failed_jobs.buckets:
            bucket_summary = self.render_bucket_summary(results)
            if bucket_summary:
                report_md += "\n\n" + bucket_summary

        return report_md

    def render_result_table(self, results: SimFlowResults) -> str:
        """Generate a Markdown string containing a table of the testplan results."""
        column_info = [
            ("Stage", "center"),
            ("Name", "center"),
            ("Tests", "left"),
            ("Max Job Runtime", "center"),
            ("Simulated Time", "center"),
            ("Passing", "center"),
            ("Total", "center"),
            ("Pass Rate", "center"),
        ]
        table = []
        hidden_names = ("n.a.", "unmapped")

        for stage_key, stage in results.stages.items():
            # Coalesce result information to default values if necessary
            stage_name = "" if stage_key.lower() in hidden_names else stage_key

            for tp_key, tp in stage.testpoints.items():
                tp_name = "" if tp_key.lower() in hidden_names else tp_key
                for test_name, result in tp.tests.items():
                    job_runtime = "" if result.max_time is None else f"{result.max_time:.3f}s"
                    sim_time = "" if result.sim_time is None else f"{result.sim_time:.3f}us"
                    pass_rate = "-- %" if result.total == 0 else f"{result.percent:.2f} %"

                    row = [
                        stage_name,
                        tp_name,
                        test_name,
                        job_runtime,
                        sim_time,
                        result.passed,
                        result.total,
                        pass_rate,
                    ]
                    table.append(row)

            pass_rate = "-- %" if stage.total == 0 else f"{stage.percent:.2f} %"
            # TODO: note the calculated stage totals are currently not correct.
            table.append(
                [stage_name, None, "**TOTAL**", None, None, stage.passed, stage.total, pass_rate]
            )

        # TODO: note the calculated overall totals are currently not correct.
        pass_rate = "-- %" if results.total == 0 else f"{results.percent:.2f} %"
        table.append(
            [None, None, "**TOTAL**", None, None, results.passed, results.total, pass_rate]
        )

        if not table:
            return ""

        return "### Test Results\n\n" + tabulate(
            table,
            headers=[c[0] for c in column_info],
            tablefmt="pipe",
            colalign=[c[1] for c in column_info],
        )

    def render_coverage_table(self, results: SimFlowResults) -> str:
        """Generate a Markdown string containing a table of the coverage results."""
        if results.coverage is None:
            return ""

        cov_results = {
            k.upper().replace("_", "/"): f"{v:.2f} %"
            for k, v in results.coverage.flattened().items()
            if v is not None
        }
        if not cov_results and not results.cov_report_page:
            return ""

        report_md = "## Coverage Results"
        if results.cov_report_page:
            report_md += f"\n### [Coverage Dashboard]({results.cov_report_page})"
        if cov_results:
            colalign = ("center",) * len(cov_results)
            report_md += "\n\n" + tabulate(
                [cov_results], headers="keys", tablefmt="pipe", colalign=colalign
            )

        return report_md

    def render_bucket_summary(self, results: SimFlowResults) -> str:
        """Generate a Markdown string with a summary of the buckets (failures/killed)."""
        lines = [(0, "## Failure Buckets")]

        for bucket, tests in sorted(
            results.failed_jobs.buckets.items(),
            key=lambda kv: len(kv[1]),
            reverse=True,
        ):
            lines.append((0, f"* `{bucket}` has {len(tests)} {_plural('failure', tests)}:"))

            grouped_tests = defaultdict(list)
            for job in tests:
                grouped_tests[job.name].append(job)

            displayed = list(grouped_tests.items())[: self.MAX_TESTS_PER_BUCKET]
            for name, reseeds in displayed:
                lines.append(
                    (1, f"* Test {name} has {len(reseeds)} {_plural('failure', reseeds)}.")
                )

                for failure in reseeds[: self.MAX_RESEEDS_PER_BUCKETED_TEST]:
                    lines.append((2, f"* {failure.qual_name}\\"))
                    line_context = "Log" if failure.line is None else f"Line {failure.line}, in log"
                    lines.append((2, f"  {line_context} {failure.log_path}"))
                    if failure.log_context:
                        lines.append((0, ""))
                        lines.extend((4, line.rstrip()) for line in failure.log_context)
                    lines.append((0, ""))

                extra = len(reseeds) - self.MAX_RESEEDS_PER_BUCKETED_TEST
                if extra > 0:
                    lines.append((2, f"* ... and {extra} more {_plural('failure', extra)}."))

            extra = len(grouped_tests) - self.MAX_TESTS_PER_BUCKET
            if extra > 0:
                lines.append((2, f"* ... and {extra} more {_plural('test', extra)}."))

        return _indent_by_levels(lines)

    def render_summary(self, summary: SimResultsSummary) -> ReportArtifacts:
        """Render a Markdown report of a summary of the sim flow results (overall)."""
        # Generate result metadata information
        if summary.top is not None:
            report_md = self.render_metadata(
                summary.top,
                summary.timestamp,
                summary.build_seed,
                title="Simulation Results (Summary)",
            )
        else:
            report_md = ""

        # Generate a table aggregating and mapping block-level reports
        table = []
        for name, flow_result in summary.flow_results.items():
            coverage = "--"
            if flow_result.coverage is not None:
                average = flow_result.coverage.average
                if average is not None:
                    coverage = f"{average:.2f} %"
            file_name = flow_result.block.variant_name()

            # Optionally display links to the block HTML reports, relative to the CWD
            if self.html_link_base is not None:
                relative = Path(self.relative_to) if self.relative_to is not None else Path.cwd()
                block_report = self.html_link_base / f"{file_name}.html"
                html_report_path = relative_to(block_report, relative)
                name_link = f"[{name.upper()}]({html_report_path!s})"
            else:
                name_link = name.upper()

            table.append(
                {
                    "Name": name_link,
                    "Passing": flow_result.passed,
                    "Total": flow_result.total,
                    "Pass Rate": f"{flow_result.percent:.2f} %",
                    "Coverage": coverage,
                }
            )

        if table:
            colalign = ("center",) * len(table[0])
            report_md += "\n\n" + tabulate(
                table, headers="keys", tablefmt="pipe", colalign=colalign
            )

        return {"report.md": report_md}


def write_report(files: ReportArtifacts, root: Path) -> None:
    """Write rendered report artifacts to the file system, relative to a given path.

    Args:
        files: the output report artifacts from rendering simulation results.
        root: the path to write the report files relative to.

    """
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def display_report(
    files: ReportArtifacts, sink: Callable[[str], None] = print, *, with_headers: bool = False
) -> None:
    """Emit the report artifacts to some textual sink.

    Prints to stdout by default, but can also write to a logger by overriding the sink.

    Args:
        files: the output report artifacts from rendering simulation results.
        sink: a callable that accepts a string. Default is `print` to stdout.
        with_headers: a boolean controlling whether to emit artifact path names as headers.

    """
    for path, content in files.items():
        header = f"\n--- {path} ---\n" if with_headers else ""
        sink(header + content + "\n")


def gen_reports(
    summary: SimResultsSummary,
    flow_results: Mapping[str, SimFlowResults],
    path: Path,
) -> None:
    """Generate and display a full set of reports for the given regression run.

    This helper currently saves JSON and HTML reports to disk (relative to the given path),
    and outputs a Markdown report to the CLI.

    Args:
        summary: overview of the block results
        flow_results: mapping flow names to detailed flow results
        path: output directory path

    """
    for renderer in (JsonReportRenderer(), HtmlReportRenderer()):
        renderer.render(
            summary=summary,
            flow_results=flow_results,
            outdir=path,
        )

    renderer = MarkdownReportRenderer(path)

    # Per-block CLI results are displayed to the `INFO` log
    if log.isEnabledFor(log.INFO):
        for flow_result in flow_results.values():
            block_name = flow_result.block.variant_name()
            log.info("[results]: [%s]", block_name)
            cli_block = renderer.render_block(flow_result)
            display_report(cli_block, sink=log.log_raw)
            log.log_raw("\n" if summary.top is None else "\n\n")

    # Summary CLI results are displayed to stdout, so long as this is a primary cfg
    if summary.top is not None:
        cli_summary = renderer.render_summary(summary)
        display_report(cli_summary)
