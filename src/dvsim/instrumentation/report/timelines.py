# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation timeline (bar chart) visualizations."""

import base64
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO

import matplotlib as mpl

# Force the headless matplotlib backend (must be done before other matplotlib imports)
mpl.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import plotly.colors as pc
import plotly.graph_objects as go
from matplotlib.ticker import MaxNLocator
from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    RenderProfile,
    make_job_metadata_hover,
    make_repeating_color_map,
    render_plotly_figure,
)
from dvsim.logging import log
from dvsim.utils import format_time_as_hms as format_time
from dvsim.utils import format_time_metric

# Threshold: after this many jobs are being rendered in a timeline, we should render the graph
# as a PNG using matplotlib instead, to improve the performance and generated report size.
DEFAULT_PNG_THRESHOLD: int = 1000

# Threshold: after this many jobs are being rendered in a timeline, we should start applying
# scaling measures to ensure the figure remains legible (in terms of general shape/structure).
TIMELINE_SCALE_THRESHOLD: int = DEFAULT_VISUALIZATION_HEIGHT_PX


@dataclass(frozen=True)
class BarInfo:
    """Information about a single bar in the rendered timeline bar chart figure."""

    base: float
    width: float
    index: int
    tooltip: str
    color: str


class TimelineBarChart(InstrumentationVisualizer):
    """Renders plotly bar chart figures showing scheduler job timeline information."""

    title = "Job Timeline"

    # Default timeline bar rendering size properties
    DEFAULT_MIN_BAR_PX: int = 2
    DEFAULT_MAX_BAR_PX: int = 50

    def __init__(
        self,
        *,
        apply_bar_scaling: bool = True,
        bar_px_range: tuple[int, int] = (DEFAULT_MIN_BAR_PX, DEFAULT_MAX_BAR_PX),
        png_threshold: int | None = DEFAULT_PNG_THRESHOLD,
    ) -> None:
        """Construct a TimelineBarChart.

        Args:
            apply_bar_scaling: Enable automatic scaling of bar thickness with bar count, to make
              bars more visible on larger graphs (at the cost of bars overlapping each other).
            bar_px_range: tuple of (min, max) range of pixels that each bar is allowed to occupy.
              Note that the minimum is only enforced if `apply_bar_scaling` is enabled.
            png_threshold: If more than this many bars are provided, the graph will be rendered as
              as a PNG using matplotlib for space & performance optimization. If set to `None`,
              this will never happen, and plotly HTML will always be rendered.

        """
        self.apply_bar_scaling: bool = apply_bar_scaling
        self.min_bar_px: int = bar_px_range[0]
        self.max_bar_px: int = bar_px_range[1]
        self.png_threshold: int | None = png_threshold

        # Margins to render the bar chart with
        self.margins: dict[str, int] = {"t": 80, "b": 40, "l": 50, "r": 20}

    def _compute_chart_height(self, num_jobs: int) -> int:
        """Compute the height that should be used for the bar chart figure."""
        vertical_margins = self.margins.get("t", 0) + self.margins.get("b", 0)
        height = num_jobs * self.max_bar_px + vertical_margins
        return min(height, DEFAULT_VISUALIZATION_HEIGHT_PX)

    def _compute_bar_thickness(self, num_jobs: int) -> float:
        """Compute the bar thickness (in visual units, not px) to use for this chart.

        Below a configured threshold (`TIMELINE_SCALE_THRESHOLD`) we always render at a minimum
        width. After this knee, we linearly scale to ensure visibility for large amounts.

        """
        if not self.apply_bar_scaling or num_jobs <= TIMELINE_SCALE_THRESHOLD:
            return 1.0
        scaled = num_jobs / TIMELINE_SCALE_THRESHOLD * self.min_bar_px
        return max(1.0, scaled)

    def _get_figure_contents(
        self, results: InstrumentationResults
    ) -> dict[str, list[BarInfo]] | None:
        """Build the figure contents for some results, mapping categories/traces to bar info."""
        # Get the job & scheduler timing info, and check enough data exists to build a graph.
        job_timings = results.job_timings()
        if not job_timings:
            return None
        jobs_by_start_time = sorted(job_timings.items(), key=lambda kv: kv[1].start_time)
        run_start_time, _ = results.get_run_time_info()

        # Determine the index of each bar by start time
        job_indices = {job_id: i for i, (job_id, _) in enumerate(jobs_by_start_time, start=1)}

        # If any relevant job metadata exists, split bars into subsets keyed by the target.
        categories: dict[str, list[str]] = defaultdict(list)
        for job_id in job_indices:
            metadata = results.jobs[job_id].meta
            key = "all" if metadata is None else metadata.target
            categories[key].append(job_id)
        categories = dict(sorted(categories.items()))
        color_map = make_repeating_color_map(categories, pc.qualitative.Plotly)

        # Get the information for all bars & traces to render in the figure
        figure_info: dict[str, list[BarInfo]] = defaultdict(list)
        for key, jobs in categories.items():
            bar_color = color_map[key]

            for job_id in jobs:
                timings = job_timings[job_id]
                metadata = results.jobs[job_id].meta
                index = job_indices[job_id]

                start_time_offset = timings.start_time - run_start_time
                end_time_offset = timings.end_time - run_start_time
                extra_timing_info = {
                    "Duration": format_time_metric(timings.duration),
                    "Start time": format_time_metric(start_time_offset),
                    "End time": format_time_metric(end_time_offset),
                }
                hover_data = make_job_metadata_hover(job_id, extra_timing_info, metadata)

                figure_info[key].append(
                    BarInfo(
                        base=start_time_offset,
                        width=timings.duration,
                        index=index,
                        tooltip=hover_data,
                        color=bar_color,
                    )
                )

        return figure_info

    def _render_plotly_figure(
        self, results: InstrumentationResults, figure_data: dict[str, list[BarInfo]], num_jobs: int
    ) -> str:
        """Render a dynamic plotly HTML visualization from the given results & figure data."""
        # Determine chart dimensions / scaling based on the number of jobs being rendered.
        run_start_time, run_end_time = results.get_run_time_info()
        height = self._compute_chart_height(num_jobs)
        bar_width = self._compute_bar_thickness(num_jobs)

        # Render the figure and configure layout & presentation
        fig = go.Figure()
        outline = (
            {"width": 0.0}
            if num_jobs <= TIMELINE_SCALE_THRESHOLD
            else {"width": 0.2, "color": "rgba(0,0,0,0.025)"}
        )

        for key, bars in figure_data.items():
            fig.add_bar(
                x=[bar.width for bar in bars],
                y=[bar.index for bar in bars],
                base=[bar.base for bar in bars],
                name=key,
                orientation="h",
                width=bar_width,
                # Plotly only allows 1 color per trace; assume bar colors are shared
                marker={"color": bars[0].color, "line": outline},
                customdata=[bar.tooltip for bar in bars],
                hovertemplate="%{customdata}<extra></extra>",
            )

        run_duration = run_end_time - run_start_time
        fig.update_layout(
            template="plotly_white",
            title_text=(
                f"<b>Gantt chart of {num_jobs:,} scheduled jobs "
                f"({format_time(run_duration, omit_zero=True)} run length)</b>"
            ),
            title_x=0.5,
            margin=self.margins,
            height=height,
        )
        fig.update_legends(title="Job Target")
        fig.update_yaxes(title="Job", autorange="reversed")
        fig.update_xaxes(showgrid=True, **PLOTLY_TIMING_AXIS_CONFIG)

        # Enforce linear integer tick scaling for small numbers of jobs to prevent automatic
        # interpolation of non-integer ticks.
        linear_tick_threshold = 10
        if num_jobs <= linear_tick_threshold:
            fig.update_yaxes(tickmode="linear", tick0=1, dtick=1)
        else:
            fig.update_yaxes(tickmode="auto", tickformat=",")

        return render_plotly_figure(fig)

    def _render_matplotlib_figure(
        self, results: InstrumentationResults, figure_data: dict[str, list[BarInfo]], num_jobs: int
    ) -> str:
        """Render a HTML fragment with a PNG generated using matplotlib from the given data."""
        # Determine chart dimensions / scaling based on the number of jobs being rendered.
        run_start_time, run_end_time = results.get_run_time_info()
        run_duration = run_end_time - run_start_time
        height = self._compute_chart_height(num_jobs)
        width = 1.25 * DEFAULT_VISUALIZATION_HEIGHT_PX  # Default aspect ratio of 5:4
        bar_width = self._compute_bar_thickness(num_jobs)

        # Determine figure scaling parameters.
        fig_scale_factor = 4  # Render a larger figure to preserve detail
        fig_height_px = int(height * fig_scale_factor)
        fig_width_px = int(width * fig_scale_factor)
        fig_dpi = 300
        fig_size = (fig_width_px / fig_dpi, fig_height_px / fig_dpi)

        # TODO: exact layout details are difficult to reconcile between plotly and matplotlib.
        # For now just ignore margin sizes in calculations & presentation and leave a warning.
        if self.margins:
            log.warning("Margin sizes ignored when rendering job timeline graph in matplotlib.")

        # Render the figure and configure layout & presentation
        fig, axes = plt.subplots(figsize=fig_size)
        bg_color = fig.get_facecolor()
        low_opacity_bg_color = (*bg_color[:3], 0.1)
        axes.barh(
            y=[bar.index for bars in figure_data.values() for bar in bars],
            width=[bar.width for bars in figure_data.values() for bar in bars],
            left=[bar.base for bars in figure_data.values() for bar in bars],
            color=[bar.color for bars in figure_data.values() for bar in bars],
            height=bar_width,
            linewidth=0.2,
            edgecolor=low_opacity_bg_color,
        )

        title = (
            f"Gantt chart of {num_jobs:,} scheduled jobs "
            f"({format_time(run_duration, omit_zero=True)} run length)"
        )
        axes.set_title(title, fontweight="bold")

        # Render the legend in the top right, just outside the graph axes.
        legend_handles = [
            mpatches.Patch(color=bars[0].color, label=key) for key, bars in figure_data.items()
        ]
        legend = axes.legend(
            handles=legend_handles,
            title="Job Target",
            alignment="left",
            title_fontsize="large",
            frameon=False,
            loc="upper left",  # corner of the legend to place
            bbox_to_anchor=(1.02, 1),  # location of the legend on the figure
            borderaxespad=0,
        )

        axes.xaxis.grid(linewidth=0.5, alpha=0.5)
        axes.set_axisbelow(True)
        axes.set_xlim(0, run_duration)
        axes.set_xlabel("Time (s)")
        axes.yaxis.grid(linewidth=0)
        axes.tick_params(axis="y", length=0)
        axes.set_ylim(0.5, num_jobs + 0.5)
        axes.set_ylabel("Job")
        axes.invert_yaxis()

        # Enforce integer tick locations to prevent automatic interpolation of non-integer ticks.
        axes.yaxis.set_major_locator(MaxNLocator(integer=True))

        # Remove spine (border) visibility
        for spine in ("top", "bottom", "left", "right"):
            axes.spines[spine].set_visible(False)

        # Make sure we have enough space to render the legend
        fig.canvas.draw()
        bbox = legend.get_window_extent()
        legend_width_inches = bbox.width / fig.dpi
        canvas_width, canvas_height = fig.get_size_inches()
        fig.set_size_inches(canvas_width + legend_width_inches, canvas_height)

        # Render the figure as a PNG
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=fig_dpi)
        png_bytes = buf.getvalue()
        plt.close(fig)

        # For now, to keep this abstraction simple, encode the image as a base64 png.
        # TODO: it might be nice to render this as a separate report artifact in the future, but
        # the `InstrumentationVisualizer` interface will need some work.
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return (
            f'<img src="data:image/png;base64,{b64}" '
            f'     onclick="window.open(this.src)" '
            f'     style="max-height:{height}px; height: auto; '
            f'            max-width: 100%; width: auto; cursor: zoom-in;" />'
            f'<div style="font-size: 0.9em;">'
            f"  Click to open the full-resolution image."
            f"</div>"
        )

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a bar chart visualization from the instrumentation results as a HTML fragment.

        If the required job timing information is not available (or there are no jobs), just
        returns `None` instead.

        """
        figure_data = self._get_figure_contents(results)
        if not figure_data:
            return None

        # Dispatch to either plotly (dynamic HTML) or matplotlib (png) based on the number of
        # jobs that need to be rendered.
        num_jobs = sum(len(jobs) for jobs in figure_data.values())
        if self.png_threshold is None or num_jobs <= self.png_threshold:
            return self._render_plotly_figure(results, figure_data, num_jobs)
        return self._render_matplotlib_figure(results, figure_data, num_jobs)

    @classmethod
    def for_profile(cls, profile: RenderProfile) -> Self:
        """Create a visualizer instance configured for a given rendering profile."""
        if profile == RenderProfile.HIGH:
            png_threshold = DEFAULT_PNG_THRESHOLD * 10
            log.debug(
                "Using render profile '%s' for '%s' visualization. Setting PNG threshold to %d.",
                profile.name,
                cls.title,
                png_threshold,
            )
            return cls(png_threshold=png_threshold)
        if profile == RenderProfile.FULL:
            log.debug(
                "Using render profile '%s' for '%s' visualization. Disabling PNG threshold.",
                profile.name,
                cls.title,
            )
            return cls(png_threshold=None)
        return cls()
