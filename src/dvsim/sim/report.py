# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate reports."""

from pathlib import Path
from typing import Protocol, TypeAlias

from dvsim.logging import log
from dvsim.sim.data import SimResultsSummary
from dvsim.templates.render import render_static, render_template

__all__ = (
    "HtmlReportRenderer",
    "JsonReportRenderer",
    "ReportRenderer",
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


def gen_reports(summary: SimResultsSummary, path: Path) -> None:
    """Generate a full set of reports for the given regression run.

    Args:
        summary: overview of the block results
        path: output directory path

    """
    for renderer in (JsonReportRenderer(), HtmlReportRenderer()):
        renderer.render(summary, outdir=path)
