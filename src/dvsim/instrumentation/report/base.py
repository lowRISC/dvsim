# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation reporting & visualizations."""

from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypeVar

import plotly.colors as pc
import plotly.graph_objects as go
import plotly.offline
from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.records import JobInstrumentationMetadata
from dvsim.logging import log
from dvsim.report.artifacts import ReportArtifacts, render_static_content
from dvsim.templates.render import render_template

__all__ = (
    "DEFAULT_VISUALIZATION_HEIGHT_PX",
    "PLOTLY_TIMING_AXIS_CONFIG",
    "InstrumentationVisualizer",
    "RenderProfile",
    "get_default_color_map",
    "make_job_metadata_hover",
    "make_repeating_color_map",
    "render_html_report",
    "render_plotly_figure",
)

# The default figure height limit in pixels that visualizations should target, if possible.
DEFAULT_VISUALIZATION_HEIGHT_PX: int = 1000

# Standard plotly timing axis/tick config options
PLOTLY_TIMING_AXIS_CONFIG: dict[str, Any] = {
    "title": "Time (s)",
    "tickformat": ",",
    "ticks": "outside",
    "tickwidth": 1,
    "ticklen": 4,
    "tickcolor": "black",
}


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


def render_plotly_figure(fig: go.Figure, *args: list[Any], **kwargs: dict[str, Any]) -> str:
    """Render a plotly figure / visualization to a HTML fragment to insert into a report.

    Args:
        fig: The plotly figure to render.
        args: Any extra arguments to pass to `fig.to_html(...)`.
        kwargs: Any extra keyword arguments to pass to `fig.to_html(...)`.

    Returns:
        The HTML fragment corresponding to the plotly Figure, without plotly.js included.

    """
    return fig.to_html(*args, full_html=False, include_plotlyjs=False, **kwargs)


def make_job_metadata_hover(
    job_id: str,
    extra: Iterable[str] | Mapping[str, str] | None,
    metadata: JobInstrumentationMetadata | None,
    *,
    omit_status: bool = False,
) -> str:
    """Make tooltip hover text for a graph item corresponding to some DVSim job.

    Args:
        job_id: The ID / full name of the job (displayed as the title).
        extra: Any extra lines or key/value mapping to insert after the title & before metadata.
        metadata: Any optional metadata to include at the end of the tooltip.
        omit_status: A flag to disable display of status metadata. Useful for combined job views,
          where jobs may have inconsistent statuses (e.g. flaky results).

    Returns:
        The tooltip hover HTML text for the job, intended to be used with plotly's `hovertemplate`.

    """
    lines = [f"<b>{job_id}</b>"]

    if extra is not None:
        if isinstance(extra, Mapping):
            for key, value in extra.items():
                lines.append(f"{key}: {value}")
        else:
            lines += list(extra)

    if metadata is not None:
        block_info = metadata.block
        if metadata.block_variant:
            block_info += f" ({metadata.block_variant})"
        lines += [
            "------------------",
            f"Name: {metadata.name}",
            f"Tool: {metadata.tool}",
            f"Block: {block_info}",
            f"Target: {metadata.target}",
        ]
        if not omit_status:
            lines.append(f"Status: {metadata.status.value}")
        if metadata.backend is not None:
            lines.append(f"Backend: {metadata.backend}")

    return "<br>".join(lines)


T = TypeVar("T")


def make_repeating_color_map(data: Iterable[str], colors: Iterable[T]) -> dict[str, T]:
    """Make a color mapping that repeats for as long as is needed to fit the amount of data.

    Args:
        data: The category strings to map to the colors.
        colors: The non-empty color items to be mapped. Repeated if needed to match `data`.

    Returns:
        The mapping from data items -> color, in a cyclically repeating order.

    """
    data = list(data)
    colors = list(colors)
    if len(colors) == 0:
        raise ValueError("Given an empty list of colors to repeat?")

    while len(colors) < len(data):
        colors += colors.copy()
    return dict(zip(data, colors, strict=False))


def get_default_color_map(categories: Sequence[str]) -> dict[str, Any]:
    """Build a color map for a chart, using large palettes for more variety as is needed."""
    palette = pc.qualitative.Plotly
    if len(categories) > len(palette):
        extra_colors = [
            pc.qualitative.Bold,
            pc.qualitative.Safe,
            pc.qualitative.Vivid,
            pc.qualitative.D3,
            pc.qualitative.Set1,
            pc.qualitative.Set2,
        ]
        extra_index = 0
        while len(categories) > len(palette) and extra_index < len(extra_colors):
            palette += extra_colors[extra_index]
            extra_index += 1
    return make_repeating_color_map(categories, palette)
