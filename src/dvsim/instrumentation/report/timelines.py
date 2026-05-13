# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation timeline (bar chart) visualizations."""

import base64
import heapq
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import matplotlib as mpl

# Force the headless matplotlib backend (must be done before other matplotlib imports)
mpl.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from matplotlib.axes import Axes
from matplotlib.figure import Figure as MplFigure
from matplotlib.ticker import MaxNLocator
from typing_extensions import Self, override

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.records import ConcreteJobTimingMetrics
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    RenderProfile,
    get_default_color_map,
    make_job_metadata_hover,
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


@dataclass(frozen=True)
class FigureData:
    """Information about the rendered timeline bar chart figure."""

    traces: dict[str, list[BarInfo]]
    indices: dict[str, int]
    num_indices: int
    num_jobs: int
    run_duration: float


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

    def _assign_indices(
        self, jobs_by_start_time: list[tuple[str, ConcreteJobTimingMetrics]]
    ) -> tuple[dict[str, int], int]:
        """Assign each job as a bar on the chart to a given index (vertical slot).

        Args:
            jobs_by_start_time: a list of (job_id, job timing) items pre-ordered by start time.

        Returns:
            A tuple of (mapping of job_id -> assigned index, num indices).

        """
        return (
            {job_id: i for i, (job_id, _) in enumerate(jobs_by_start_time, start=1)},
            len(jobs_by_start_time),
        )

    def _compute_chart_height(self, num_indices: int) -> int:
        """Compute the height that should be used for the bar chart figure."""
        vertical_margins = self.margins.get("t", 0) + self.margins.get("b", 0)
        height = num_indices * self.max_bar_px + vertical_margins
        return min(height, DEFAULT_VISUALIZATION_HEIGHT_PX)

    def _compute_bar_thickness(self, num_indices: int) -> float:
        """Compute the bar thickness (in visual units, not px) to use for this chart.

        Below a configured threshold (`TIMELINE_SCALE_THRESHOLD`) we always render at a minimum
        width. After this knee, we linearly scale to ensure visibility for large amounts.

        """
        if not self.apply_bar_scaling or num_indices <= TIMELINE_SCALE_THRESHOLD:
            return 1.0
        scaled = num_indices / TIMELINE_SCALE_THRESHOLD * self.min_bar_px
        return max(1.0, scaled)

    def _extra_hover_info(
        self, _job_id: str, _results: InstrumentationResults, _index: int
    ) -> dict[str, str]:
        """Get a key->value mapping of extra items to put in the job's tooltip."""
        return {}

    def _get_figure_contents(self, results: InstrumentationResults) -> FigureData | None:
        """Build the figure contents for some results, mapping categories/traces to bar info."""
        # Get the job & scheduler timing info, and check enough data exists to build a graph.
        job_timings = results.job_timings()
        if not job_timings:
            return None
        jobs_by_start_time = sorted(job_timings.items(), key=lambda kv: kv[1].start_time)
        run_start_time, run_end_time = results.get_run_time_info()
        run_duration = run_end_time - run_start_time

        # Determine the index of each bar by start time
        job_indices, num_indices = self._assign_indices(jobs_by_start_time)

        # If any relevant job metadata exists, split bars into subsets keyed by the target.
        categories: dict[str, list[str]] = defaultdict(list)
        for job_id in job_indices:
            metadata = results.jobs[job_id].meta
            key = "all" if metadata is None else metadata.target
            categories[key].append(job_id)
        categories = dict(sorted(categories.items()))
        color_map = get_default_color_map(list(categories.keys()))

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
                extra_timing_info.update(**self._extra_hover_info(job_id, results, index))
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

        num_jobs = sum(len(jobs) for jobs in categories.values())
        return FigureData(
            traces=figure_info,
            indices=job_indices,
            num_indices=num_indices,
            num_jobs=num_jobs,
            run_duration=run_duration,
        )

    def _get_plotly_outline_info(self, num_indices: int) -> dict[str, Any] | None:
        """Get the bar marker outline information to use for this Plotly figure.

        Below a configured threshold (TIMELINE_SCALE_THRESHOLD), we render as normal. When the
        number of jobs exceeds this threshold, we make bar outlines less distinctive to avoid
        small bars overlapping and combining to blot out parts of the graph.
        """
        if num_indices <= TIMELINE_SCALE_THRESHOLD:
            return None
        return {"width": 0.2, "color": "rgba(0,0,0,0.025)"}

    def _build_plotly_layout(self, fig: go.Figure, figure_data: FigureData) -> None:
        """Build the layout / presentation options for the Plotly figure."""
        height = self._compute_chart_height(figure_data.num_indices)

        fig.update_layout(
            template="plotly_white",
            title_text=(
                f"<b>Gantt chart of {figure_data.num_jobs:,} scheduled jobs "
                f"({format_time(figure_data.run_duration, omit_zero=True)} run length)</b>"
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
        if figure_data.num_indices <= linear_tick_threshold:
            fig.update_yaxes(tickmode="linear", tick0=1, dtick=1)
        else:
            fig.update_yaxes(tickmode="auto", tickformat=",")

    def _render_plotly_figure(self, figure_data: FigureData) -> str:
        """Render a dynamic plotly HTML visualization from the given results & figure data."""
        # Determine chart scaling based on the number of jobs being rendered.
        bar_width = self._compute_bar_thickness(figure_data.num_indices)
        outline = self._get_plotly_outline_info(figure_data.num_indices)

        # Render the figure and configure layout & presentation
        fig = go.Figure()

        for key, bars in figure_data.traces.items():
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

        self._build_plotly_layout(fig, figure_data)
        return render_plotly_figure(fig)

    def _build_matplotlib_layout(self, fig: MplFigure, axes: Axes, figure_data: FigureData) -> None:
        """Build the layout / presentation options for the matplotlib figure."""
        title = (
            f"Gantt chart of {figure_data.num_jobs:,} scheduled jobs "
            f"({format_time(figure_data.run_duration, omit_zero=True)} run length)"
        )
        axes.set_title(title, fontweight="bold")

        # Render the legend in the top right, just outside the graph axes.
        legend_handles = [
            mpatches.Patch(color=bars[0].color, label=key)
            for key, bars in figure_data.traces.items()
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
        axes.set_xlim(0, figure_data.run_duration)
        axes.set_xlabel("Time (s)")
        axes.yaxis.grid(linewidth=0)
        axes.tick_params(axis="y", length=0)
        axes.set_ylim(0.5, figure_data.num_indices + 0.5)
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

    def _render_matplotlib_figure(self, figure_data: FigureData) -> str:
        """Render a HTML fragment with a PNG generated using matplotlib from the given data."""
        # Determine chart dimensions / scaling based on the number of jobs being rendered.
        height = self._compute_chart_height(figure_data.num_indices)
        width = 1.25 * DEFAULT_VISUALIZATION_HEIGHT_PX  # Default aspect ratio of 5:4
        bar_width = self._compute_bar_thickness(figure_data.num_indices)

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
            y=[bar.index for bars in figure_data.traces.values() for bar in bars],
            width=[bar.width for bars in figure_data.traces.values() for bar in bars],
            left=[bar.base for bars in figure_data.traces.values() for bar in bars],
            color=[bar.color for bars in figure_data.traces.values() for bar in bars],
            height=bar_width,
            linewidth=0.2,
            edgecolor=low_opacity_bg_color,
        )
        self._build_matplotlib_layout(fig, axes, figure_data)

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
        if figure_data is None or not figure_data.traces:
            return None

        # Dispatch to either plotly (dynamic HTML) or matplotlib (png) based on the number of
        # jobs that need to be rendered.
        if self.png_threshold is None or figure_data.num_jobs <= self.png_threshold:
            return self._render_plotly_figure(figure_data)
        return self._render_matplotlib_figure(figure_data)

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


class ParallelismChart(TimelineBarChart):
    """A squashed timeline that shows the (simulated) parallelism in scheduling a run's jobs."""

    title = "Job Parallelism"

    def __init__(self, png_threshold: int | None = DEFAULT_PNG_THRESHOLD) -> None:
        """Construct a class ParallelismChart(TimelineBarChart):.

        Args:
            png_threshold: If more than this many bars are provided, the graph will be rendered as
              as a PNG using matplotlib for space & performance optimization. If set to `None`,
              this will never happen, and plotly HTML will always be rendered.

        """
        super().__init__(apply_bar_scaling=True, png_threshold=png_threshold)

    def _assign_indices(
        self, jobs_by_start_time: list[tuple[str, ConcreteJobTimingMetrics]]
    ) -> tuple[dict[str, int], int]:
        """Squash the bar chart by assigning each job to the first unoccupied parallel index.

        Args:
            jobs_by_start_time: a list of (job_id, job timing) items pre-ordered by start time.

        Returns:
            A tuple of (mapping of job_id -> assigned index, num indices).

        """
        active: list[tuple[float, int]] = []  # heap of (end time, slot ID)
        free_slots: list[int] = []  # heap of free slots
        assignments: dict[str, int] = {}  # assignments of (job ID -> slot ID)
        next_slot_id: int = 1

        # Greedy assignment to get the maximum amount of parallelism (this is a lane assignment
        # / interval coloring problem). Instead of just maintaining a heap of active slots, we
        # update an additional heap for free slots to ensure we always make the first possible
        # assignment for each job. This results in more comprehensible & cleaner graphs.
        for job_id, timing in jobs_by_start_time:
            while active and active[0][0] <= timing.start_time:
                _, slot = heapq.heappop(active)
                heapq.heappush(free_slots, slot)

            if free_slots:
                slot = heapq.heappop(free_slots)
            else:
                slot = next_slot_id
                next_slot_id += 1
            assignments[job_id] = slot
            heapq.heappush(active, (timing.end_time, slot))

        return assignments, next_slot_id - 1

    @override
    def _get_plotly_outline_info(self, num_indices: int) -> dict[str, Any] | None:
        """Get the bar marker outline information to use for this Plotly figure.

        When showing a parallelism chart, we always render without outlines, to avoid them
        overlapping to form solid blocks (less visually comprehensible).
        """
        return {"width": 0.0}

    def _extra_hover_info(
        self, _job_id: str, _results: InstrumentationResults, index: int
    ) -> dict[str, str]:
        """Get a key-value mapping of extra items to put in the job's tooltip."""
        return {"Parallel slot": str(index)}

    def _build_plotly_layout(self, fig: go.Figure, figure_data: FigureData) -> None:
        """Build the layout / presentation options for the Plotly figure."""
        super()._build_plotly_layout(fig, figure_data)
        fig.update_layout(
            title_text=(
                f"<b>Job Parallelism Visualization "
                f"({format_time(figure_data.run_duration, omit_zero=True)} run length)</b>"
            )
        )
        fig.update_yaxes(title="Parallel slot")

        # For parallelism charts, use 'overlay' mode so different target traces (categories)
        # in the same index are rendered with the same vertical offset
        fig.update_layout(barmode="overlay")

    def _build_matplotlib_layout(self, fig: MplFigure, axes: Axes, figure_data: FigureData) -> None:
        """Build the layout / presentation options for the matplotlib figure."""
        super()._build_matplotlib_layout(fig, axes, figure_data)
        title = (
            f"Job Parallelism Visualization "
            f"({format_time(figure_data.run_duration, omit_zero=True)} run length)"
        )
        axes.set_title(title, fontweight="bold")
        axes.set_ylabel("Parallel slot")

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a parallelism visualization from the instrumentation results as a HTML fragment.

        Also computes some additional metrics and appends them as a simple paragraph at the end
        of the fragment. If the required job timing information is not available (or there are no
        jobs), just returns `None` instead.

        """
        figure_data = self._get_figure_contents(results)
        if figure_data is None or not figure_data.traces:
            return None

        # Dispatch to either plotly (dynamic HTML) or matplotlib (png) based on the number of
        # jobs that need to be rendered.
        if self.png_threshold is None or figure_data.num_jobs <= self.png_threshold:
            rendered_fig = self._render_plotly_figure(figure_data)
        else:
            rendered_fig = self._render_matplotlib_figure(figure_data)

        # Add some additional metrics (as text) describing the scheduling efficiency
        available_compute_time = figure_data.num_indices * figure_data.run_duration
        if available_compute_time == 0:
            return rendered_fig
        useful_work_time = sum(job_timing.duration for job_timing in results.job_timings().values())
        utilization = useful_work_time / available_compute_time
        metrics = {
            "Degree of parallelism": str(figure_data.num_indices),
            "Wallclock time": format_time_metric(figure_data.run_duration, omit_zero=True),
            "Available compute time": format_time_metric(available_compute_time, omit_zero=True),
            "Time running jobs": format_time_metric(useful_work_time, omit_zero=True),
            "Parallel utilization": f"{utilization:.3%}",
        }
        rendered_fig += (
            "<p>" + "<br>".join(f"<b>{key}</b>: {value}" for key, value in metrics.items()) + "</p>"
        )
        return rendered_fig
