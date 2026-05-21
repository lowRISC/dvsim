# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation usage (time series concurrency) visualizations."""

from collections import defaultdict
from collections.abc import Callable

import plotly.graph_objects as go
from plotly.graph_objs import Figure

from dvsim.instrumentation.records import (
    ConcreteJobTimingMetrics,
    InstrumentationResults,
    JobInstrumentationResults,
)
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    get_default_color_map,
    render_plotly_figure,
)


class ConcurrencyLineGraph(InstrumentationVisualizer):
    """Renders plotly time series figures showing usage / concurrency info over time."""

    title = "Job Concurrency"

    # Default height in pixels for a usage/concurrency chart visualization
    DEFAULT_CHART_HEIGHT_PX: int = 800

    def __init__(
        self, *, group_fn: Callable[[JobInstrumentationResults], str] | None = None
    ) -> None:
        """Construct a ConcurrencyLineGraph.

        Args:
            group_fn: A function to partition jobs into distinct (non-overlapping) subsets,
              by the category string that is returned. Defaults to `None`, meaning that no
              partitioning is applied.

        """
        self.group_fn: Callable[[JobInstrumentationResults], str] | None = group_fn

    def concurrency_events(
        self, job_timings: dict[str, ConcreteJobTimingMetrics]
    ) -> list[tuple[float, int]]:
        """Retrieve a list of concurrency events (changes in concurrency) for the given timings.

        Args:
            job_timings: A mapping of job IDs to timing metrics to get concurrency for.

        Returns:
            An ordered time-series list of tuples (time in seconds, number of concurrent jobs).

        """
        start_times = [(timing.start_time, 1) for timing in job_timings.values()]
        end_times = [(timing.end_time, -1) for timing in job_timings.values()]
        job_events = sorted(start_times + end_times)

        concurrency_events: list[tuple[float, int]] = []
        concurrency = 0
        for event_time, delta in job_events:
            concurrency += delta  # (cumulative sum so far)
            concurrency_events.append((event_time, concurrency))

        return concurrency_events

    def _build(self, results: InstrumentationResults) -> Figure | None:
        """Build the plotly time series line graph figure for the given results."""
        job_timings = results.job_timings()
        if not job_timings:
            return None

        run_start_time, run_end_time = results.get_run_time_info()
        run_duration = run_end_time - run_start_time

        # Group jobs into subsets keyed by the configured `group_fn`.
        categories: dict[str, list[str]] = defaultdict(list)
        for job_id in job_timings:
            if self.group_fn is not None:
                key = self.group_fn(results.jobs[job_id])
                categories[key].append(job_id)
            else:
                categories["Concurrent Jobs"].append(job_id)
        categories = dict(sorted(categories.items()))
        color_map = get_default_color_map(list(categories.keys()))

        # For each group, get concurrency events and plot them as a trace.
        fig = go.Figure()
        for key, jobs in categories.items():
            subset_timings = {job_id: job_timings[job_id] for job_id in jobs}
            concurrency_events = self.concurrency_events(subset_timings)
            event_times = [event[0] - run_start_time for event in concurrency_events]
            concurrency_vals = [event[1] for event in concurrency_events]

            fig.add_scatter(
                x=event_times,
                y=concurrency_vals,
                name=key,
                mode="lines",
                marker={"color": color_map[key]},
            )

        # Extra layout / formatting settings
        height = min(self.DEFAULT_CHART_HEIGHT_PX, DEFAULT_VISUALIZATION_HEIGHT_PX)
        fig.update_layout(
            template="plotly_white",
            title_text="<b>Job Concurrency over Time</b>",
            title_x=0.5,
            margin={"t": 40},
            height=height,
        )
        fig.update_yaxes(title="Number of Concurrent Jobs", showgrid=True, tickformat=",")
        fig.update_xaxes(range=[0, run_duration], showgrid=True, **PLOTLY_TIMING_AXIS_CONFIG)

        # If we have multiple categories, show information about all series when hovering
        if len(categories) > 1:
            fig.update_layout(hovermode="x unified")

        return fig

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a time series line graph from the instrumentation results as a HTML fragment.

        If the required job timing information is not available (or there are no jobs), just
        returns `None` instead.

        """
        fig = self._build(results)
        if fig is None:
            return None

        # Always render as HTML; we need > 100k jobs to make considering a PNG worthwhile.
        return render_plotly_figure(fig)


class ToolUsageLineGraph(ConcurrencyLineGraph):
    """Time series chart showing concurrent tool usage over the run's lifetime."""

    title = "Tool Concurrency"

    def __init__(self) -> None:
        """Construct a ToolUsageLineGraph."""
        super().__init__(group_fn=self._get_job_tool)

    def _get_job_tool(self, job: JobInstrumentationResults) -> str:
        """Get the tool from a job's recorded metadata, or 'Unknown' if it does not exist."""
        if job.meta is None:
            return "Unknown"

        return job.meta.tool

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a tool usage line graph from the instrumentation results as a HTML fragment.

        If the required job timing or metadata information is not available (or there are no
        jobs), just returns `None` instead.

        """
        if all(job.meta is None for job in results.jobs.values()):
            return None

        fig = self._build(results)
        if fig is None:
            return None

        fig.update_layout(title_text="<b>Tool Concurrency over Time</b>")
        fig.update_legends(title="Tool")

        return render_plotly_figure(fig)
