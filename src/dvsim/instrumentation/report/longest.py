# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation bar chart visualizations of the longest jobs & tests."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import plotly.graph_objects as go
from typing_extensions import Self

from dvsim.instrumentation import InstrumentationResults
from dvsim.instrumentation.records import (
    ConcreteJobTimingMetrics,
    JobInstrumentationMetadata,
    JobInstrumentationResults,
)
from dvsim.instrumentation.report.base import (
    DEFAULT_VISUALIZATION_HEIGHT_PX,
    PLOTLY_TIMING_AXIS_CONFIG,
    InstrumentationVisualizer,
    RenderProfile,
    get_default_color_map,
    make_job_metadata_hover,
    render_plotly_figure,
)
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.utils import format_time_metric, ordinal_suffix


@dataclass(frozen=True)
class TestAggregateInfo:
    """Computed aggregate information about a test in a scheduler run."""

    name: str  # name of the test
    jobs: list[str]  # list of job IDs for different test seeds, sorted by duration, descending
    duration: float  # combined test duration, in seconds
    ordinal: int  # position / ranking relative to all tests, by decreasing duration
    timings: dict[str, ConcreteJobTimingMetrics]  # mapping from test jobs to their timings


class LongestBarChart(InstrumentationVisualizer):
    """Renders plotly bar chart figures that rank the longest jobs in the scheduler."""

    title = "Longest Jobs"

    # Standard layout & formatting configuration
    MAX_NAME_CHARS: int = 40
    DROPDDOWN_KEY_THRESHOLD: int = 5
    ALL_KEY: str = "All categories"

    # The default maximum number of bars and stacked bars (jobs per test) to render for each trace
    DEFAULT_MAX_BARS: int = 250
    DEFAULT_MAX_JOBS_PER_BAR: int = 6

    def __init__(  # noqa: PLR0913
        self,
        *,
        category_fn: Callable[[JobInstrumentationResults], str] | None = None,
        color_fn: Callable[[str], Any] | None = None,
        group_tests: bool = False,
        max_bars: int | None = DEFAULT_MAX_BARS,
        max_jobs_per_bar: int | None = None,
        allow_missing_meta: bool = False,
        allow_isomorphic: bool = False,
    ) -> None:
        """Construct a LongestBarChart.

        Args:
            category_fn: Optional function to split jobs into groups by category. The top N items
              will be displayed for each category, with a button to show each trace. If `None`,
              only an "overall" trace is shown.
            color_fn: Optional function to provide color mapping information for specific groups.
            group_tests: Flag to group jobs of the same test by name. This allows timing results
              for the same tests to be combined in a stacked bar view.
            max_bars: The maximum number of bars to show in each group (& overall).
            max_jobs_per_bar: If group_tests=True, the maximum number of stacked bars to
              render per bar. If there are too many bars to display, the bottom
              (N - max_jobs_per_bar + 1) jobs will be combined into a single bar.
            allow_missing_meta: Whether the figure should still render even if metadata is missing.
            allow_isomorphic: Whether the figure should still render even if the mapped tests are
              isomorphic to the jobs (i.e. each job is 1-to-1 with a test; there is no extra info
              provided by grouping the tests despite trying).

        """
        if not group_tests and max_jobs_per_bar:
            log.warning("Setting max_jobs_per_bar is meaningless without grouping jobs into tests")
        if not group_tests and allow_isomorphic:
            log.warning("Setting allow_isomorphic is meaningless without grouping jobs into tests")

        self.category_fn = category_fn
        self.color_fn = color_fn
        self.group_tests = group_tests
        self.max_bars = max_bars
        self.max_jobs_per_bar = max_jobs_per_bar
        self.allow_missing_meta = allow_missing_meta
        self.allow_isomorphic = allow_isomorphic

        # Default margin layout information
        self.margins = {"t": 100, "b": 40, "l": 160, "r": 40}

    def get_job_test(self, job_id: str, job: JobInstrumentationResults) -> str | None:
        """Get the test name for a given job (should be the same for all seeds of a given test)."""
        if job.meta is None:
            return None

        # Do not group non-test jobs (building, coverage merging and reporting).
        # These can be identified by their lack of seeds at the end of their IDs.
        if not job_id.strip().split(".")[-1].isdigit():
            return job_id

        variant_name = job.meta.block
        if job.meta.block_variant:
            variant_name += f"_{job.meta.block_variant}"
        return f"{variant_name}:{job.meta.name}"

    def _get_job_color(
        self, color_map: dict[str, str], job: JobInstrumentationResults, key: str
    ) -> str:
        """Get the color to render a job bar."""
        if self.category_fn is not None:
            return color_map[self.category_fn(job)]
        return color_map[key]

    def _compute_test_aggregates(
        self, results: InstrumentationResults
    ) -> dict[str, TestAggregateInfo]:
        """Combine jobs into tests (if enabled) and compute aggregate information about tests.

        Args:
            results: The instrumentation results to compute test aggregates for.

        Returns:
            A mapping of (test name -> aggregate info), ordered by decreasing duration.

        """
        job_timings = results.job_timings()
        if not job_timings:
            return {}

        longest_jobs = sorted(job_timings.items(), key=lambda kv: kv[1].duration, reverse=True)

        # Group jobs into tests if configured to do so
        jobs_per_test: dict[str, list[str]] = defaultdict(list)
        test_durations: dict[str, float] = defaultdict(float)
        for job_id, timing in longest_jobs:
            if self.group_tests:
                test_group = self.get_job_test(job_id, results.jobs[job_id]) or job_id
                jobs_per_test[test_group].append(job_id)
                test_durations[test_group] += timing.duration
            else:
                # If no test grouping function is given, tests are isomorphic to jobs
                jobs_per_test[job_id].append(job_id)
                test_durations[job_id] = timing.duration

        # If we get no additional data from grouping, we optionally stop rendering here.
        if (
            self.group_tests
            and not self.allow_isomorphic
            and len(jobs_per_test) == len(job_timings)
        ):
            log.debug("Not emitting grouped graph '%s' due to test isomorphism", self.title)
            return {}

        longest_tests = sorted(test_durations.items(), key=lambda kv: kv[1], reverse=True)
        test_ordinals = {test_group: i for i, (test_group, _) in enumerate(longest_tests, start=1)}

        # Aggregate info about each test together, returning in order of decreasing duration
        return {
            test: TestAggregateInfo(
                name=test,
                jobs=jobs_per_test[test],
                duration=test_durations[test],
                ordinal=ordinal,
                timings={job: job_timings[job] for job in jobs_per_test[test]},
            )
            for test, ordinal in test_ordinals.items()
        }

    def _get_top_tests_by_category(
        self, results: InstrumentationResults, tests: dict[str, TestAggregateInfo], limit: int
    ) -> dict[str, list[str]]:
        """Split test items into categories and get the top N tests of each category.

        Args:
            results: The instrumentation results.
            tests: The mapping of tests computed from the instrumentation results.
            limit: The maximum number of jobs to be computed for each category.

        Returns:
            A mapping of (category -> list of tests), where each list of tests is sorted in
            descending ranked order. A special case category (`self.ALL_KEY`) is also available,
            with the top N tests in all categories combined.

        """
        # Split tests into categories and get the top tests of each category.
        top_by_category: dict[str, list[str]] = defaultdict(list)
        top_by_category[self.ALL_KEY] = [t.name for t in list(tests.values())[:limit]]

        for test_group, test_info in tests.items():
            if self.category_fn is None:
                continue

            # If we are grouping jobs into tests, check that they all report the same category.
            # If they for some reason do not, warn and just choose the first one.
            keys = {job_id: self.category_fn(results.jobs[job_id]) for job_id in test_info.jobs}
            unique_keys = set(keys.values())
            test_group_key = next(iter(unique_keys))
            if len(unique_keys) != 1:
                log.error(
                    "Got multiple different categories for jobs in the same test group (%s): %s\n"
                    "Using the first key '%s' as a fallback.",
                    test_group,
                    keys,
                    test_group_key,
                )
            if len(top_by_category[test_group_key]) < limit:
                top_by_category[test_group_key].append(test_group)

        return top_by_category

    def _make_combined_bar_info(
        self,
        test: TestAggregateInfo,
        jobs: list[str],
        meta: JobInstrumentationMetadata | None,
    ) -> tuple[float, str]:
        """Get information for a bar that combines a subset of a test's jobs/seeds.

        Args:
            test: The test to create a combined bar for.
            jobs: The jobs (subset of test.jobs) to create a combined bar for.
            meta: Metadata about the test/jobs, if any exists.

        Returns:
            A tuple (combined duration, tooltip hover text) for the combined bar.

        """
        if not jobs:
            raise ValueError("Cannot make a combined bar from a subset of no jobs.")

        num_combined_jobs = len(jobs)
        job_durations = [test.timings[job_id].duration for job_id in jobs]

        total_duration = sum(job_durations)
        max_duration = max(job_durations)
        min_duration = min(job_durations)
        avg_duration = total_duration / num_combined_jobs
        rank_str = f"{test.ordinal}{ordinal_suffix(test.ordinal)} longest"
        extra_timing_info = [
            f"{num_combined_jobs} other jobs (combined)",
            f"Number of seeds: {len(test.jobs)}",
            f"Test duration (all seeds combined): {format_time_metric(test.duration)}",
            f"Test ranking (all seeds combined): {rank_str}",
            f"Combined duration: {format_time_metric(total_duration)}",
            f"Maximum duration: {format_time_metric(max_duration)}",
            f"Mean duration: {format_time_metric(avg_duration)}",
            f"Minimum duration: {format_time_metric(min_duration)}",
        ]
        hover = make_job_metadata_hover(test.name, extra_timing_info, meta)

        return total_duration, hover

    def _make_trace(
        self,
        results: InstrumentationResults,
        test_info: list[TestAggregateInfo],
        color_map: dict[str, str],
    ) -> go.Bar:
        """Get a plotly bar trace for a group of tests using some defined color mapping."""
        # Determine max sizes for left-padding ordinals
        max_ordinal = max(test.ordinal for test in test_info)
        ordinal_len = len(str(max_ordinal))

        job_names, durations, hovers, marker_colors = [], [], [], []
        for test in test_info:
            # Display jobs within groups shortest to longest (shortest bars first)
            jobs = list(reversed(test.jobs))
            first_job = results.jobs[jobs[0]]
            marker_color = self._get_job_color(color_map, first_job, test.name)

            # Due to a limitation in plotly's presentation, we cannot have auto tick scaling
            # (which is needed for the size of our data) with tickmode="array", which we also
            # need to be able to provide custom names, because job IDs are too long.
            # To work around this, we define shortened names that are guaranteed to be unique,
            # by prefixing them with their ordinal position (ranking).
            id_prefix = (
                test.name
                if len(test.name) <= self.MAX_NAME_CHARS
                else test.name[: self.MAX_NAME_CHARS - 3] + "..."
            )
            display_name = f"{test.ordinal:0{ordinal_len}d}: {id_prefix} "

            # It might be too slow (and too much data) to display all the bars. If configured to
            # do so, combine the smallest bars.
            max_jobs = self.max_jobs_per_bar or len(jobs)
            num_combined_jobs = len(jobs) - max_jobs + 1
            if num_combined_jobs <= 1:
                num_combined_jobs = 0  # If we only have 1 job to "combine", just add it normally

            if num_combined_jobs:
                meta = first_job.meta
                duration, hover = self._make_combined_bar_info(test, jobs[:num_combined_jobs], meta)
                job_names.append(display_name)
                durations.append(duration)
                hovers.append(hover)
                marker_colors.append(marker_color)

            # Render the remainder of the jobs in full detail
            for job_id in jobs[num_combined_jobs:]:
                timings = test.timings[job_id]

                extra_timing_info = {}
                rank_str = f"{test.ordinal}{ordinal_suffix(test.ordinal)} longest"
                if self.group_tests:
                    extra_timing_info.update(
                        {
                            "Number of seeds": str(len(jobs)),
                            "Test duration (all seeds combined)": format_time_metric(test.duration),
                            "Test ranking (all seeds combined)": rank_str,
                        }
                    )
                else:
                    extra_timing_info["Job ranking"] = rank_str
                extra_timing_info["Duration"] = format_time_metric(timings.duration)
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
        if not self.allow_missing_meta and all(job.meta is None for job in results.jobs.values()):
            return None

        # Group jobs into tests if configured to do so, and compute relevant aggregate information.
        # Tests are ordered by decreasing duration.
        tests = self._compute_test_aggregates(results)
        num_tests = len(tests)
        if num_tests == 0:
            return None

        # Determine item limits & title formatting from the configured max bars & grouping.
        item_type = "tests" if self.group_tests else "jobs"
        if self.max_bars is None or num_tests <= self.max_bars:
            num_visible = num_tests
            title_item_desc = f"{num_tests:,} {item_type}"
        else:
            num_visible = self.max_bars
            title_item_desc = f"top {num_visible} of {num_tests} {item_type}"

        # Bin the tests by category (up to top `num_visible` for each). Ensure that the 'All'
        # category is always ordered first.
        top_by_category = self._get_top_tests_by_category(results, tests, num_visible)
        categories = sorted(top_by_category, key=lambda c: (c != self.ALL_KEY, c))
        num_categories = len(categories)

        if self.color_fn is not None:
            color_map = {key: self.color_fn(key) for key in categories}
        elif self.category_fn is not None:
            # We don't need a colour for `self.ALL_KEY`, so exclude it.
            color_map = get_default_color_map(categories[1:])
        else:
            color_map = get_default_color_map(categories)

        # For each category, create a bar trace & menu (visibility) toggle button.
        traces: list[go.Bar] = []
        menu_buttons: list[dict[str, Any]] = []
        for i, key in enumerate(categories):
            test_info = [tests[test_group] for test_group in top_by_category[key]]
            traces.append(self._make_trace(results, test_info, color_map))
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
            title_text=f"<b>{item_type.capitalize()} by longest duration ({title_item_desc})</b>",
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


class LongestByToolChart(LongestBarChart):
    """Renders plotly bar chart figures that rank the longest jobs or tests, partitioned by tool."""

    title = "Longest Jobs by Tool"

    def __init__(
        self,
        *,
        group_tests: bool = False,
        max_bars: int | None = LongestBarChart.DEFAULT_MAX_BARS,
        max_jobs_per_bar: int | None = None,
    ) -> None:
        """Construct a LongestByToolChart.

        Args:
            group_tests: Flag to group jobs of the same test by name. This allows timing results
              for the same tests to be combined in a stacked bar view.
            max_bars: The maximum number of bars to show for each tool (and overall).
            max_jobs_per_bar: If group_tests=True, the maximum number of stacked bars to
              render per bar. If there are too many bars to display, the bottom
              (N - max_jobs_per_bar + 1) jobs will be combined into a single bar.

        """
        super().__init__(
            group_tests=group_tests,
            category_fn=self._get_job_tool,
            max_bars=max_bars,
            max_jobs_per_bar=max_jobs_per_bar,
        )

    def _get_job_tool(self, job: JobInstrumentationResults) -> str:
        """Get the tool from a job's recorded metadata, or 'Unknown' if it does not exist."""
        return "Unknown" if job.meta is None else job.meta.tool


class LongestTestsByToolChart(LongestByToolChart):
    """Renders plotly bar chart figures that rank the longest tests, partitioned by tool."""

    title = "Longest Tests by Tool"

    DEFAULT_MAX_BARS: int = 75

    def __init__(
        self,
        *,
        max_bars: int | None = DEFAULT_MAX_BARS,
        max_jobs_per_bar: int | None = LongestByToolChart.DEFAULT_MAX_JOBS_PER_BAR,
    ) -> None:
        """Construct a LongestTestsByToolChart.

        Args:
            max_bars: The maximum number of bars to show for each tool (and overall).
            max_jobs_per_bar: The maximum number of stacked bars to render per bar. If there are
              too many bars to display, the bottom (N - max_jobs_per_bar + 1) jobs will be combined
              into a single bar.

        """
        super().__init__(group_tests=True, max_bars=max_bars, max_jobs_per_bar=max_jobs_per_bar)

    @classmethod
    def for_profile(cls, profile: RenderProfile) -> Self:
        """Create a visualizer instance configured for a given rendering profile."""
        if profile == RenderProfile.HIGH:
            max_bars = cls.DEFAULT_MAX_BARS * 4
            max_jobs_per_bar = (cls.DEFAULT_MAX_JOBS_PER_BAR - 1) * 4 + 1
            log.debug(
                "Using render profile '%s' for '%s' visualization. Setting max bars to %d "
                "and max jobs per bar to %d.",
                profile.name,
                cls.title,
                max_bars,
                max_jobs_per_bar,
            )
            return cls(max_bars=max_bars, max_jobs_per_bar=max_jobs_per_bar)
        if profile == RenderProfile.FULL:
            log.debug(
                "Using render profile '%s' for '%s' visualization. Disabling max bars and "
                "max jobs per bar.",
                profile.name,
                cls.title,
            )
            return cls(max_bars=None, max_jobs_per_bar=None)
        return cls()


class LongestByBlockChart(LongestBarChart):
    """Renders plotly bar charts that rank the longest jobs or tests, partitioned by block."""

    title = "Longest Jobs by Block"

    DEFAULT_MAX_BARS: int = 50

    def __init__(
        self,
        *,
        group_tests: bool = False,
        max_bars: int | None = DEFAULT_MAX_BARS,
        max_jobs_per_bar: int | None = None,
    ) -> None:
        """Construct a LongestByBlockChart.

        Args:
            group_tests: Flag to group jobs of the same test by name. This allows timing results
              for the same tests to be combined in a stacked bar view.
            max_bars: The maximum number of bars to show for each block (and overall).
            max_jobs_per_bar: If group_tests=True, the maximum number of stacked bars to
              render per bar. If there are too many bars to display, the bottom
              (N - max_jobs_per_bar + 1) jobs will be combined into a single bar.

        """
        super().__init__(
            max_bars=max_bars,
            max_jobs_per_bar=max_jobs_per_bar,
            category_fn=self._get_job_block_variant,
            group_tests=group_tests,
        )

    def _get_job_block_variant(self, job: JobInstrumentationResults) -> str:
        """Get the block (variant) from a job's metadata, or 'Unknown' if it does not exist."""
        if job.meta is None:
            return "Unknown"

        return job.meta.block + (f"_{job.meta.block_variant}" if job.meta.block_variant else "")


class LongestTestsByBlockChart(LongestByBlockChart):
    """Renders plotly bar charts that rank the longest tests, partitioned by block."""

    title = "Longest Tests by Block"

    DEFAULT_MAX_BARS: int = 20

    def __init__(
        self,
        *,
        max_bars: int | None = DEFAULT_MAX_BARS,
        max_jobs_per_bar: int | None = LongestByBlockChart.DEFAULT_MAX_JOBS_PER_BAR,
    ) -> None:
        """Construct a LongestTestsByBlockChart.

        Args:
            max_bars: The maximum number of bars to show for each block (and overall).
            max_jobs_per_bar: The maximum number of stacked bars to render per bar. If there are
              too many bars to display, the bottom (N - max_jobs_per_bar + 1) jobs will be combined
              into a single bar.

        """
        super().__init__(group_tests=True, max_bars=max_bars, max_jobs_per_bar=max_jobs_per_bar)

    @classmethod
    def for_profile(cls, profile: RenderProfile) -> Self:
        """Create a visualizer instance configured for a given rendering profile."""
        if profile == RenderProfile.HIGH:
            max_bars = cls.DEFAULT_MAX_BARS * 5
            max_jobs_per_bar = (cls.DEFAULT_MAX_JOBS_PER_BAR - 1) * 5 + 1
            log.debug(
                "Using render profile '%s' for '%s' visualization. Setting max bars to %d "
                "and max jobs per bar to %d.",
                profile.name,
                cls.title,
                max_bars,
                max_jobs_per_bar,
            )
            return cls(max_bars=max_bars, max_jobs_per_bar=max_jobs_per_bar)
        if profile == RenderProfile.FULL:
            log.debug(
                "Using render profile '%s' for '%s' visualization. Disabling max bars and "
                "max jobs per bar.",
                profile.name,
                cls.title,
            )
            return cls(max_bars=None, max_jobs_per_bar=None)
        return cls()
