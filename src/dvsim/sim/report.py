# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate reports."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeAlias

from dvsim.logging import log
from dvsim.sim.data import SimFlowResults, SimResultsSummary
from dvsim.templates.render import render_static, render_template

__all__ = (
    "HtmlReportRenderer",
    "JsonReportRenderer",
    "MarkdownReportRenderer",
    "ReportRenderer",
    "display_report",
    "gen_reports",
    "write_report",
)

# Report rendering returns mappings of relative report paths to (string) contents.
ReportArtifacts: TypeAlias = dict[str, str]


class ReportRenderer(Protocol):
    """Renders/formats result reports, returning mappings of relative paths to (string) content."""

    format_name: str

    def render(self, summary: SimResultsSummary, outdir: Path | None = None) -> ReportArtifacts:
        """Render a report of the sim flow results into output artifacts."""
        ...


class JsonReportRenderer:
    """Renders/dumps a JSON report of the sim results."""

    format_name = "json"

    def render(self, summary: SimResultsSummary, outdir: Path | None = None) -> ReportArtifacts:
        """Render a JSON report of the sim flow results into output artifacts."""
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)

        artifacts = {}

        for results in summary.flow_results.values():
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

    def render(self, summary: SimResultsSummary, outdir: Path | None = None) -> ReportArtifacts:
        """Render a HTML report of the sim flow results into output artifacts."""
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)

        artifacts = {}

        # Generate block HTML pages
        for results in summary.flow_results.values():
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

    def render(self, summary: SimResultsSummary, outdir: Path | None = None) -> ReportArtifacts:
        """Render a Markdown report of the sim flow results."""
        if outdir is not None:
            outdir.mkdir(parents=True, exist_ok=True)

        report_md = [
            self.render_block(flow_result)["report.md"]
            for flow_result in summary.flow_results.values()
        ]
        report_md.append(self.render_summary(summary)["report.md"])

        report = "\n".join(report_md)
        if outdir is not None:
            (outdir / "report.md").write_text(report)

        return {"report.md": report}

    def render_block(self, results: SimFlowResults) -> ReportArtifacts:
        """Render a Markdown report of the sim flow results for a given block/flow."""
        _results = results
        return {"report.md": "TODO: Markdown block report"}

    def render_summary(self, summary: SimResultsSummary) -> ReportArtifacts:
        """Render a Markdown report of a summary of the sim flow results (overall)."""
        _summary = summary
        return {"report.md": "TODO: Markdown summary report"}


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


def gen_reports(summary: SimResultsSummary, path: Path) -> None:
    """Generate and display a full set of reports for the given regression run.

    This helper currently saves JSON and HTML reports to disk (relative to the given path),
    and outputs a Markdown report to the CLI.

    Args:
        summary: overview of the block results
        path: output directory path

    """
    for renderer in (JsonReportRenderer(), HtmlReportRenderer()):
        renderer.render(summary, outdir=path)

    renderer = MarkdownReportRenderer()

    # Per-block CLI results are displayed to the `INFO` log
    if log.isEnabledFor(log.INFO):
        for flow_result in summary.flow_results.values():
            block_name = flow_result.block.variant_name()
            log.info("[results]: [%s]", block_name)
            cli_block = renderer.render_block(flow_result)
            display_report(cli_block, sink=log.log_raw)
            log.log_raw("\n")

    # Summary CLI results are displayed to stdout, so long as this is a primary cfg
    if summary.top is not None:
        cli_summary = renderer.render_summary(summary)
        display_report(cli_summary)
