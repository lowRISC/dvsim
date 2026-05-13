# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation bar chart visualizations of the longest jobs."""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

import plotly.colors as pc
import plotly.graph_objects as go
from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.records import (
    ConcreteJobTimingMetrics,
    JobInstrumentationResults,
)
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    RenderProfile,
    make_job_metadata_hover,
    make_repeating_color_map,
    render_plotly_figure,
)
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.utils import format_time_metric, ordinal_suffix


class LongestBarChart(InstrumentationVisualizer):
    """Renders plotly bar chart figures that rank the longest jobs in the scheduler."""

    title = "Longest Jobs"

    # Standard layout & formatting configuration
    MAX_NAME_CHARS: int = 40
    DROPDDOWN_KEY_THRESHOLD: int = 5
    ALL_KEY: str = "All categories"

    # The default maximum number of bars to render for each trace (category)
    DEFAULT_MAX_BARS: int = 250

    def __init__(
        self,
        *,
        category_fn: Callable[[JobInstrumentationResults], str] | None = None,
        color_fn: Callable[[str], Any] | None = None,
        max_bars: int | None = DEFAULT_MAX_BARS,
        allow_missing_meta: bool = False,
    ) -> None:
        """Construct a LongestBarChart.

        Args:
            category_fn: Optional function to split jobs into groups by category. The top N items
              will be displayed for each category, with a button to show each trace. If `None`,
              only an "overall" trace is shown.
            color_fn: Optional function to provide color mapping information for specific groups.
            max_bars: The maximum number of bars to show in each group (& overall).
            allow_missing_meta: Whether the figure should still render even if metadata is missing.

        """
        self.category_fn = category_fn
        self.color_fn = color_fn
        self.max_bars = max_bars
        self.allow_missing_meta = allow_missing_meta

        # Default margin layout information
        self.margins = {"t": 100, "b": 40, "l": 160, "r": 40}

    def _get_job_color(
        self, color_map: dict[str, str], job: JobInstrumentationResults, key: str
    ) -> str:
        """Get the color to render a job bar."""
        if self.category_fn is not None:
            return color_map[self.category_fn(job)]
        return color_map[key]

    def _get_top_jobs_by_category(
        self, results: InstrumentationResults, jobs: list[str], limit: int
    ) -> dict[str, list[str]]:
        """Split jobs into categories and get the top N jobs of each category.

        Args:
            results: The instrumentation results.
            jobs: The list of jobs (sorted by descending duration) to filter & group.
            limit: The maximum number of jobs to be computed for each category.

        Returns:
            A mapping of (category -> list of jobs), where the list of jobs are sorted in
            descending ranked order. A special case category (`self.ALL_KEY`) is also available,
            with the top N jobs in all categories combined.

        """
        # Split jobs into categories and get the top jobs of each category.
        top_by_category: dict[str, list[str]] = defaultdict(list)
        top_by_category[self.ALL_KEY] = jobs[:limit]
        if self.category_fn is None:
            return top_by_category

        for job_id in jobs:
            key = self.category_fn(results.jobs[job_id])
            if len(top_by_category[key]) < limit:
                top_by_category[key].append(job_id)

        return top_by_category

    def _make_trace(
        self,
        results: InstrumentationResults,
        jobs: list[str],
        job_timings: dict[str, ConcreteJobTimingMetrics],
        job_ordinals: dict[str, int],
        color_map: dict[str, str],
    ) -> go.Bar:
        """Get a plotly bar trace for a group of jobs using some defined color mapping."""
        # Determine max sizes for left-padding ordinals
        max_ordinal = max(job_ordinals[job_id] for job_id in jobs)
        ordinal_len = len(str(max_ordinal))

        job_names, durations, hovers, marker_colors = [], [], [], []
        for job_id in jobs:
            timings = job_timings[job_id]
            ordinal = job_ordinals[job_id]
            marker_color = self._get_job_color(color_map, results.jobs[job_id], job_id)

            # Due to a limitation in plotly's presentation, we cannot have auto tick scaling
            # (which is needed for the size of our data) with tickmode="array", which we also
            # need to be able to provide custom names, because job IDs are too long.
            # To work around this, we define shortened names that are guaranteed to be unique,
            # by prefixing them with their ordinal position (ranking).
            id_prefix = (
                job_id
                if len(job_id) <= self.MAX_NAME_CHARS
                else job_id[: self.MAX_NAME_CHARS - 3] + "..."
            )
            display_name = f"{ordinal:0{ordinal_len}d}: {id_prefix} "

            extra_timing_info = {
                "Job ranking": f"{ordinal}{ordinal_suffix(ordinal)} longest",
                "Duration": format_time_metric(timings.duration),
            }
            meta = results.jobs[job_id].meta
            hover = make_job_metadata_hover(job_id, extra_timing_info, meta)

            job_names.append(display_name)
            durations.append(timings.duration)
            hovers.append(hover)
            marker_colors.append(marker_color)

        return go.Bar(
            orientation="h",
            x=durations,
            y=job_names,
            customdata=hovers,
            marker_color=marker_colors,
            hovertemplate="%{customdata}<extra></extra>",
            visible=False,  # traces are all hidden by default
        )

    def render(self, results: InstrumentationResults) -> str | None:
        """Render a bar chart from the instrumentation results as a HTML fragment.

        If the required job timing (and optionally the metadata) information is not available,
        or there are no jobs, this just returns `None` instead.

        """
        job_timings = results.job_timings()
        if not job_timings:
            return None
        if not self.allow_missing_meta and all(job.meta is None for job in results.jobs.values()):
            return None

        # Order jobs by their duration (descending) and determine ordinals/rankings for each.
        longest_jobs = sorted(job_timings.items(), key=lambda kv: kv[1].duration, reverse=True)
        job_ordinals = {job_id: i for i, (job_id, _) in enumerate(longest_jobs, start=1)}
        num_jobs = len(longest_jobs)

        # Determine item limits & title formatting from the configured max bars.
        if self.max_bars is None or num_jobs <= self.max_bars:
            num_visible = num_jobs
            title_item_desc = f"{num_jobs:,} jobs"
        else:
            num_visible = self.max_bars
            title_item_desc = f"top {num_visible} of {num_jobs} jobs"

        # Bin the jobs by category (up to top `num_visible` for each). Ensure that the 'All'
        # category is always ordered first.
        ordered_jobs = [job_id for (job_id, _) in longest_jobs]
        top_by_category = self._get_top_jobs_by_category(results, ordered_jobs, num_visible)
        categories = sorted(top_by_category, key=lambda c: (c != self.ALL_KEY, c))
        num_categories = len(categories)

        if self.color_fn is not None:
            color_map = {key: self.color_fn(key) for key in categories}
        else:
            color_map = make_repeating_color_map(categories, pc.qualitative.Plotly)

        # For each category, create a bar trace & menu (visibility) toggle button.
        traces: list[go.Bar] = []
        menu_buttons: list[dict[str, Any]] = []
        for i, key in enumerate(categories):
            jobs = top_by_category[key]
            traces.append(self._make_trace(results, jobs, job_timings, job_ordinals, color_map))
            menu_buttons.append(
                {
                    "label": key,
                    "method": "update",
                    "args": [{"visible": [j == i for j in range(num_categories)]}],
                }
            )
        traces[0].visible = True

        # Display buttons for <= some arbitrary threshold, otherwise use a dropdown.
        # TODO: A better solution would dynamically choose the type based on the contents & layout.
        updatemenu_type, updatemenu_direction = (
            ("buttons", "right")
            if num_categories <= self.DROPDDOWN_KEY_THRESHOLD
            else ("dropdown", "down")
        )

        # Create the final figure from the constructed list of traces & buttons.
        # Configure extra layout / formatting settings.
        fig = go.Figure(data=traces)
        fig.update_layout(
            template="plotly_white",
            showlegend=False,
            title_text=f"<b>Jobs by longest duration ({title_item_desc})</b>",
            title_xanchor="center",
            title_y=0.97,
            title_x=0.5,
            margin=self.margins,
            height=DEFAULT_VISUALIZATION_HEIGHT_PX,
            bargap=0.05,
        )
        fig.update_yaxes(autorange="reversed")

        duration_config = PLOTLY_TIMING_AXIS_CONFIG.copy()
        duration_config["title"] = "Duration (s)"
        fig.update_xaxes(showgrid=True, **duration_config)

        # Only render the 'All' button if we have at least 2 other categories to render
        if len(menu_buttons[1:]) == 1:
            menu_buttons = menu_buttons[1:]
        if menu_buttons:
            fig.update_layout(
                updatemenus=[
                    {
                        "buttons": menu_buttons,
                        "type": updatemenu_type,
                        "direction": updatemenu_direction,
                        "showactive": True,
                        "x": 0.0,
                        "xanchor": "left",
                        "y": 1.055,
                        "bgcolor": "rgba(230,230,230,0.9)",
                        "bordercolor": "rgba(0,0,0,0)",
                        "borderwidth": 0,
                        "pad": {"r": 8, "t": 0, "b": 0},
                        "font_size": 13,
                    }
                ],
            )

        return render_plotly_figure(fig)

    @classmethod
    def for_profile(cls, profile: RenderProfile) -> Self:
        """Create a visualizer instance configured for a given rendering profile."""
        if profile == RenderProfile.HIGH:
            max_bars = cls.DEFAULT_MAX_BARS * 4
            log.debug(
                "Using render profile '%s' for '%s visualization. Setting max bars to %d.",
                profile.name,
                cls.title,
                max_bars,
            )
            return cls(max_bars=max_bars)
        if profile == RenderProfile.FULL:
            log.debug(
                "Using render profile '%s' for '%s' visualization. Disabling max bars.",
                profile.name,
                cls.title,
            )
            return cls(max_bars=None)
        return cls()


class LongestByStatusChart(LongestBarChart):
    """Renders plotly bar chart figures that rank the longest jobs, optionally split by status."""

    def __init__(self, *, max_bars: int | None = LongestBarChart.DEFAULT_MAX_BARS) -> None:
        """Construct a LongestJobsByStatusChart.

        Args:
            max_bars: The maximum number of bars to show for each status (and overall).

        """
        super().__init__(
            max_bars=max_bars,
            category_fn=self._get_job_status,
            color_fn=self._get_status_color,
            allow_missing_meta=True,
        )

    def _get_job_status(self, job: JobInstrumentationResults) -> str:
        """Get the status from a job's recorded metadata, or 'Unknown' if it does not exist."""
        return "Unknown" if job.meta is None else job.meta.status.value

    def _get_status_color(self, status: str) -> str:
        """Get the (hex code string) color that a given job status should render with."""
        misc_color = "#808080"
        if status in (LongestBarChart.ALL_KEY, "Unknown"):
            return misc_color

        try:
            job_status = JobStatus(status)
        except ValueError:
            log.warning("Got unexpected job status: %s in instrumentation chart", status)
            return misc_color

        color_mapping = {
            JobStatus.PASSED: "#04B34F",
            JobStatus.FAILED: "#BF1B00",
            JobStatus.KILLED: "#12436D",
        }
        return color_mapping.get(job_status, misc_color)
