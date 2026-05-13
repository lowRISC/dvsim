# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation reporting & visualizations."""

import base64
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypeVar

import plotly.offline
from plotly.graph_objs import Figure
from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.records import JobInstrumentationMetadata
from dvsim.logging import log
from dvsim.report.artifacts import ReportArtifacts, render_static_content
from dvsim.templates.render import render_template

__all__ = (
    "DEFAULT_PNG_THRESHOLD",
    "DEFAULT_VISUALIZATION_HEIGHT_PX",
    "PLOTLY_HTML_FRAGMENT_CONFIG",
    "PLOTLY_TIMING_AXIS_CONFIG",
    "InstrumentationVisualizer",
    "RenderProfile",
    "make_job_metadata_hover",
    "make_repeating_color_map",
    "render_html_report",
    "render_large_figure",
)

# The default figure height limit in pixels that visualizations should target, if possible.
DEFAULT_VISUALIZATION_HEIGHT_PX: int = 1000

# The default number of jobs / data points above which graphs should be rendered as PNGs, instead
# of dynamic HTML, to improve performance and generated report size.
DEFAULT_PNG_THRESHOLD: int = 1000

# The rendering configuration to use when rendering a graph as a PNG
PNG_SCALE_FACTOR: float = 2.0

# Standard plotly kwargs for rendering a HTML figure as an instrumentation report fragment.
PLOTLY_HTML_FRAGMENT_CONFIG: dict[str, Any] = {
    "full_html": False,
    "include_plotlyjs": False,
}

# Standard plotly timing tick config options
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
        log.debug("Render profile %s not used by visualization '%s'", profile.name, cls.__name__)
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
    for i, vis in enumerate(visualizations or [], start=1):
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

    metrics_json_path = None if json_path is None else json_path
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


def render_large_figure(
    fig: Figure,
    *,
    num_points: int | None = None,
    interactivity_limit: int | None = DEFAULT_PNG_THRESHOLD,
    png_width: int | None = None,
    png_height: int | None = None,
) -> str:
    """Render a potentially large plotly figure depending upon its size compared to some threshold.

    Args:
        fig: The figure to render.
        num_points: The number of points/bars/entities in the figure.
        interactivity_limit: Over this limit, render as a PNG instead of dynamic HTML.
          If None, there is no limit and this will always render as dynamic HTML.
        png_width: If rendering as a PNG, use this width. If not given, try to use the figure's
          width defined on its layout. As a last resort, use `DEFAULT_VISUALIZATION_HEIGHT_PX`.
        png_height: If rendering as a PNG, use this height. If not given, try to use the figure's
          height defined on its layout. As a last resort, use `DEFAULT_VISUALIZATION_HEIGHT_PX`.

    Returns:
        A HTML string fragment comprising either the dynamic graph HTML or the encoded PNG.

    """
    if num_points is None or interactivity_limit is None or num_points <= interactivity_limit:
        return fig.to_html(**PLOTLY_HTML_FRAGMENT_CONFIG)

    log.debug(
        "Plotly figure with %d points is larger than threshold %d.", num_points, interactivity_limit
    )

    width = fig.layout.width if png_width is None else png_width
    width = DEFAULT_VISUALIZATION_HEIGHT_PX if width is None else width
    height = fig.layout.height if png_height is None else png_height
    height = DEFAULT_VISUALIZATION_HEIGHT_PX if height is None else height
    log.debug(
        "Rendering the figure as a PNG with dimensions (%dx%d) with scale %g...",
        width,
        height,
        PNG_SCALE_FACTOR,
    )

    png = fig.to_image(format="png", width=width, height=height, scale=PNG_SCALE_FACTOR)
    b64 = base64.b64encode(png).decode("ascii")

    # For now, to keep this abstraction simple, encode the image as a base64 png.
    # TODO: it might be nice to render this image as a separate report artifact in the future.
    return (
        f'<img src="data:image/png;base64,{b64}" '
        f'     onclick="window.open(this.src)" '
        f'     style="max-height:{DEFAULT_VISUALIZATION_HEIGHT_PX}px; height: auto; '
        f'            width: 100%; cursor: zoom-in;" />'
        f'<div style="font-size: 0.9em;">'
        f"  Click to open the full-resolution image"
        f"</div>"
    )


def make_job_metadata_hover(
    title: str,
    extra: Iterable[str] | Mapping[str, str] | None,
    metadata: JobInstrumentationMetadata | None,
    *,
    omit_status: bool = False,
) -> str:
    """Make a hover tooltip for a graph item corresponding to some DVSim job.

    Args:
        title: The tooltip title - normally the ID / full name of the job.
        extra: Any extra lines or key/value mapping to put after the title & before the metadata.
        metadata: Any optional metadata to include at the end of the tooltip.
        omit_status: A flag to disable display of status metadata. Useful for combined job views.

    Returns:
        The hover tooltip HTML for the job to use with plotly's `hovertemplate`.

    """
    lines = [f"<b>{title}</b>"]

    if extra is not None:
        if isinstance(extra, Mapping):
            for key, value in extra.items():
                lines.append(f"{key.capitalize()}: {value}")
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
            lines.append(f"Status: {metadata.status}")
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
        The mapping from data items -> color in a cyclically repeating order.

    """
    data = list(data)
    colors = list(colors)
    if len(colors) == 0:
        raise ValueError("Given an empty list of colors to repeat?")

    while len(colors) < len(data):
        colors += colors.copy()
    return dict(zip(data, colors, strict=False))
