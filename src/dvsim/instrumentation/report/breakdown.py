# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation breakdown (pie & bar chart) visualizations."""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

import plotly.colors as pc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.records import JobInstrumentationResults
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    make_repeating_color_map,
    render_plotly_figure,
)
from dvsim.utils import format_time_as_hms as format_time
from dvsim.utils import format_time_metric


class BreakdownVisualization(InstrumentationVisualizer):
    """Renders pie & bar-chart figures showing job duration breakdown via some grouping."""

    title = "Job Breakdown"

    # Standard layout & formatting configuration
    MIN_PIE_HEIGHT_PX: int = 600
    MAX_BAR_PX: int = 50
    # (percentages in [0,1], i.e. 0.02 = 2%)
    PIE_LABEL_THRESHOLD: float = 0.02
    PIE_HOLE_FRACTION: float = 0.6
    PIE_SEGMENT_PULL: float = 0.03
    SUBPLOT_SPACING: float = 0.12

    def __init__(
        self, *, group_type: str, group_fn: Callable[[JobInstrumentationResults], str]
    ) -> None:
        """Construct a BreakdownVisualization.

        Args:
            group_type: The name of the key that jobs are being split into groups on (e.g. "tool").
            group_fn: A function for splitting jobs into unique groups (returns a string category).

        """
        self.group_type = group_type
        self.group_fn = group_fn

        # Default margin layout information
        self.margins = {"t": 80, "b": 40, "l": 50, "r": 20}

    def _get_color_map(self, categories: dict[str, list[str]]) -> dict[str, Any]:
        """Build a colour map for the chart, using large palettes for more variety as is needed."""
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

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a breakdown (pie/bar chart) from the instrumentation results as a HTML fragment.

        If the required job timing information is not available (or there are no jobs), just
        returns `None` instead.

        """
        job_timings = results.job_timings()
        if not job_timings:
            return None

        # Group jobs into subsets keyed by the configured `group_fn`.
        categories: dict[str, list[str]] = defaultdict(list)
        group_durations: dict[str, float] = defaultdict(float)
        for job_id in job_timings:
            key = self.group_fn(results.jobs[job_id])
            categories[key].append(job_id)
            group_durations[key] += job_timings[job_id].duration
        total_duration = sum(group_durations.values())
        if total_duration <= 0.0:
            return None

        categories = dict(sorted(categories.items()))
        color_map = self._get_color_map(categories)

        # Determine the chart dimensions for the different subplots
        pie_chart_height = min(self.MIN_PIE_HEIGHT_PX, DEFAULT_VISUALIZATION_HEIGHT_PX)
        vertical_margins = self.margins.get("t", 0) + self.margins.get("b", 0)
        axes_height = len(categories) * self.MAX_BAR_PX + vertical_margins
        bar_chart_height = min(DEFAULT_VISUALIZATION_HEIGHT_PX * 2 - pie_chart_height, axes_height)
        total_height = pie_chart_height + bar_chart_height
        row_heights = [pie_chart_height / total_height, bar_chart_height / total_height]

        # Draw 2 subplots of the same data - a pie chart on top & a bar chart on bottom.
        fig = make_subplots(
            rows=2,
            cols=1,
            row_heights=row_heights,
            vertical_spacing=self.SUBPLOT_SPACING,
            specs=[[{"type": "pie"}], [{"type": "bar"}]],
        )

        sorted_durations = sorted(group_durations.items(), key=lambda kv: kv[1], reverse=True)
        keys, durations = zip(*sorted_durations, strict=True)
        percentages = [duration / total_duration for duration in durations]
        colors = [color_map[key] for key in keys]
        display_text = [
            f"{key}<br>{pct:.2%}" if pct > self.PIE_LABEL_THRESHOLD else ""
            for key, pct in zip(keys, percentages, strict=True)
        ]
        hovers = [
            (
                f"{self.group_type.capitalize()}: {key}<br>"
                f"Number of jobs: {len(categories[key])}<br>"
                f"Total duration: {format_time_metric(duration, omit_zero=True)}<br>"
                f"Percentage: {pct:.2%}"
            )
            for key, duration, pct in zip(keys, durations, percentages, strict=True)
        ]

        fig.add_trace(
            go.Pie(
                labels=keys,
                values=durations,
                text=display_text,
                textinfo="text",
                textposition="outside",
                showlegend=False,
                hole=self.PIE_HOLE_FRACTION,
                pull=self.PIE_SEGMENT_PULL,
                marker={"colors": colors},
                customdata=hovers,
                hovertemplate="%{customdata}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        # Bar chart traces must be added individually to allow filtering via the legend.
        texts = [format_time(duration, omit_zero=True) for duration in durations]
        for key, duration, text, color, hover in zip(
            keys, durations, texts, colors, hovers, strict=True
        ):
            fig.add_trace(
                go.Bar(
                    y=[key],
                    x=[duration],
                    name=key,
                    text=[text],
                    orientation="h",
                    textposition="outside",
                    textangle=0,
                    cliponaxis=False,
                    showlegend=True,
                    marker={"color": color},
                    customdata=[hover],
                    hovertemplate="%{customdata}<extra></extra>",
                ),
                row=2,
                col=1,
            )

        # Extra layout / formatting settings
        fig.update_layout(
            template="plotly_white",
            title_text=f"<b>Total job runtime per {self.group_type.lower()}</b>",
            title_x=0.125,
            title_xanchor="left",
            margin=self.margins,
            height=total_height,
            bargap=0.1,
        )
        fig.update_legends(
            title=self.group_type.capitalize(),
            x=1.02,
            y=row_heights[1] * 0.4,
            xanchor="left",
            yanchor="middle",
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(showgrid=True, **PLOTLY_TIMING_AXIS_CONFIG)

        return render_plotly_figure(fig)


class ToolBreakdown(BreakdownVisualization):
    """Breakdown pie/bar chart showing aggregated job duration per tool used."""

    title = "Runtime per Tool"

    def __init__(self) -> None:
        """Construct a ToolBreakdown."""
        super().__init__(group_type="tool", group_fn=self._get_job_tool)

    def _get_job_tool(self, job: JobInstrumentationResults) -> str:
        """Get the tool from a job's recorded metadata, or 'Unknown' if it does not exist."""
        if job.meta is None:
            return "Unknown"

        return job.meta.tool

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a per-tool breakdown graph from the instrumentation results as a HTML fragment.

        If the required job timing or metadata information is not available (or there are no
        jobs), just returns `None` instead.

        """
        if all(job.meta is None for job in results.jobs.values()):
            return None

        return super().render(results)
