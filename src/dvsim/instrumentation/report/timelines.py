# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation timeline (bar chart) visualizations."""

from collections import defaultdict
from typing import Any

import plotly.colors as pc
import plotly.graph_objects as go

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    make_job_metadata_hover,
    make_repeating_color_map,
    render_plotly_figure,
)
from dvsim.utils import format_time_as_hms as format_time
from dvsim.utils import format_time_metric

# Threshold: after this many jobs are being rendered in a timeline, we should start applying
# scaling measures to ensure the figure remains legible (in terms of general shape/structure).
TIMELINE_SCALE_THRESHOLD: int = DEFAULT_VISUALIZATION_HEIGHT_PX


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
    ) -> None:
        """Construct a TimelineBarChart.

        Args:
            apply_bar_scaling: Enable automatic scaling of bar thickness with bar count, to make
              bars more visible on larger graphs (at the cost of bars overlapping each other).
            bar_px_range: tuple of (min, max) range of pixels that each bar is allowed to occupy.
              Note that the minimum is only enforced if `apply_bar_scaling` is enabled.

        """
        self.apply_bar_scaling: bool = apply_bar_scaling
        self.min_bar_px: int = bar_px_range[0]
        self.max_bar_px: int = bar_px_range[1]

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

    def _get_marker_info(self, num_jobs: int, bar_color: str) -> dict[str, Any]:
        """Get the bar marker information to use for this chart.

        Below a configured threshold (TIMELINE_SCALE_THRESHOLD), we render as normal. When the
        number of jobs exceeds this threshold, we make bar outlines less distinctive to avoid
        small bars overlapping and combining to blot out parts of the graph.

        """
        if num_jobs <= TIMELINE_SCALE_THRESHOLD:
            return {"color": bar_color}
        return {"color": bar_color, "line": {"width": 0.2, "color": "rgba(0,0,0,0.025)"}}

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a bar chart visualization from the instrumentation results as a HTML fragment.

        If the required job timing information is not available (or there are no jobs), just
        returns `None` instead.

        """
        # Get the job & scheduler timing info, and check enough data exists to build a graph.
        job_timings = results.job_timings()
        if not job_timings:
            return None
        jobs_by_start_time = sorted(job_timings.items(), key=lambda kv: kv[1].start_time)
        run_start_time, run_end_time = results.get_run_time_info()

        # Determine the index of each bar by start time
        job_indices = {job_id: i for i, (job_id, _) in enumerate(jobs_by_start_time)}
        num_jobs = len(jobs_by_start_time)

        # If any relevant job metadata exists, split bars into subsets keyed by the target.
        categories: dict[str, list[str]] = defaultdict(list)
        for job_id in job_indices:
            metadata = results.jobs[job_id].meta
            key = "all" if metadata is None else metadata.target
            categories[key].append(job_id)
        categories = dict(sorted(categories.items()))
        color_map = make_repeating_color_map(categories, pc.qualitative.Plotly)

        # Determine scaling factors so the bars remain visible for large numbers of jobs.
        clamped_height = self._compute_chart_height(num_jobs)
        bar_width = self._compute_bar_thickness(num_jobs)

        # Render the chart itself
        fig = go.Figure()
        for key, jobs in categories.items():
            bar_color = color_map[key]
            marker_info = self._get_marker_info(num_jobs, bar_color)

            durations, start_times, hovers, indices = [], [], [], []
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

                durations.append(timings.duration)
                start_times.append(start_time_offset)
                hovers.append(hover_data)
                indices.append(index)

            fig.add_bar(
                x=durations,
                y=indices,
                base=start_times,
                name=key,
                orientation="h",
                width=bar_width,
                marker=marker_info,
                customdata=hovers,
                hovertemplate="%{customdata}<extra></extra>",
            )

        # Extra layout / formatting settings
        run_duration = run_end_time - run_start_time
        fig.update_layout(
            template="plotly_white",
            title_text=(
                f"<b>Gantt chart of {num_jobs:,} scheduled jobs "
                f"({format_time(run_duration, omit_zero=True)} run length)</b>"
            ),
            title_x=0.5,
            margin=self.margins,
            height=clamped_height,
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
