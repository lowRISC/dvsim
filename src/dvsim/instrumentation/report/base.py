# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation reporting & visualizations."""

from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Protocol

import plotly.offline
from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.logging import log
from dvsim.report.artifacts import ReportArtifacts, render_static_content
from dvsim.templates.render import render_template

__all__ = (
    "InstrumentationVisualizer",
    "RenderProfile",
    "render_html_report",
)


class RenderProfile(Enum):
    """Levels of visualization rendering detail, which impact report size & responsiveness."""

    NORMAL = "normal"
    HIGH = "high"
    FULL = "full"


class InstrumentationVisualizer(Protocol):
    """Builder & renderer for HTML instrumentation visualizations."""

    # A short name / title of the visualization, used in the HTML report navigation tab
    title: str

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a visualization from the instrumentation results as a HTML fragment.

        If the required data is not provide in the instrumentation results (e.g. not enough
        data, or not the correct type of data recorded), or the visualization should not be
        generated, this can also optionally return `None`.

        """
        ...

    @classmethod
    def for_profile(cls, profile: RenderProfile) -> Self:
        """Create a visualizer instance configured for a given rendering profile (if supported)."""
        log.debug("Render profile %s not used by visualization '%s'", profile.name, cls.title)
        return cls()


def render_html_report(
    results: InstrumentationResults,
    *,
    visualizations: Sequence[InstrumentationVisualizer] | None = None,
    outdir: Path | None = None,
    json_path: Path | None = None,
) -> ReportArtifacts:
    """Render a HTML instrumentation report for some results & visualizations.

    Args:
        results: The instrumentation results to generate a report from.
        visualizations: The list of visualizations (if any) to display in the report.
        outdir: The optional directory to write the 'metrics.html' report to, if desired.
        json_path: Optional path to the 'metrics.json' file.

    Returns:
        The generated file contents for the report - 'metrics.html' and static CSS/JS content.

    """
    log.info("Rendering instrumentation HTML report...")

    visualizations = visualizations or []
    renders: list[tuple[InstrumentationVisualizer, str]] = []
    for i, vis in enumerate(visualizations, start=1):
        log.debug(
            "Attempting to render instrumentation visualization: %s [%d/%d]",
            vis.title,
            i,
            len(visualizations),
        )
        render = vis.render(results)
        if render is not None:
            log.info("Rendered instrumentation visualization: %s", vis.title)
            renders.append((vis, render))

    metrics_json_path = json_path
    if metrics_json_path and outdir and metrics_json_path.is_relative_to(outdir):
        metrics_json_path = metrics_json_path.relative_to(outdir)
    if outdir is not None:
        outdir.mkdir(parents=True, exist_ok=True)

    artifacts = {}

    # Render the visualizations to a single metrics.html file
    artifacts["metrics.html"] = render_template(
        path="reports/instrumentation_report.html",
        data={"renders": renders, "metrics_json": metrics_json_path},
    )
    if outdir is not None:
        report_path = outdir / "metrics.html"
        report_path.write_text(artifacts["metrics.html"])
        log.info("HTML instrumentation report written to %s", report_path)

    # Render static content needed for the report
    artifacts.update(
        render_static_content(
            static_files=[
                "css/style.css",
                "css/bootstrap.min.css",
                "js/bootstrap.bundle.min.js",
                "js/htmx.min.js",
            ],
            outdir=outdir,
        )
    )

    # Render static plotly.js separately. We generate the static minified JS from the plotly
    # library itself to make sure we are using the correct version.
    if renders:
        plotly_js_path = "js/plotly.min.js"
        artifacts[plotly_js_path] = plotly.offline.get_plotlyjs()
        if outdir is not None:
            (outdir / plotly_js_path).write_text(artifacts[plotly_js_path])

    return artifacts
