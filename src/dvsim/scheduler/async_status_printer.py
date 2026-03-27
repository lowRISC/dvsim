# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job status printing during a scheduled run."""

import asyncio
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence

from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus


class StatusPrinter(ABC):
    """Status Printer abstract base class.

    Contains core functionality related to status printing - a print interval can be configured
    to control how often the scheduler target statuses are printed, which is managed by an async
    thread. Optionally, the print interval can be configured to 0 to run in an update-driven mode
    where every single status update is printed. Regardless of the configured print interval, the
    final job update for each target is printed immediately to reflect final target end timings.
    """

    # How often we print by default. Zero means we should print on every event change.
    print_interval = 0

    def __init__(self, jobs: Sequence[JobSpec], print_interval: int | None = None) -> None:
        """Construct the base StatusPrinter."""
        # Mapping from target -> (Mapping from status -> count)
        self._target_counts: dict[str, dict[JobStatus, int]] = defaultdict(lambda: defaultdict(int))
        # Mapping from target -> number of jobs
        self._totals: dict[str, int] = defaultdict(int)

        for job in jobs:
            self._target_counts[job.target][JobStatus.SCHEDULED] += 1
            self._totals[job.target] += 1

        # The number of characters used to represent the largest field in the displayed table
        self._field_width = max((len(str(total)) for total in self._totals.values()), default=0)

        # State tracking for the StatusPrinter
        self._start_time: float = 0.0
        self._last_print: float = 0.0
        self._running: dict[str, list[str]] = defaultdict(list)
        self._num_finished: dict[str, int] = defaultdict(int)
        self._finish_time: dict[str, float] = {}

        # Async target status update handling
        self._task: asyncio.Task | None = None
        self._paused: bool = False

        self._interval = print_interval if print_interval is not None else self.print_interval

    @property
    def updates_every_event(self) -> bool:
        """If the configured print interval is 0, statuses are updated on every state change."""
        return self._interval <= 0

    def start(self) -> None:
        """Start printing the status of the scheduled jobs."""
        self._start_time = time.monotonic()
        self._print_header()
        for target in self._target_counts:
            self._init_target(target, self._get_target_row(target))

        # If we need an async task to manage the print interval, create one
        if not self.updates_every_event:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """Run a timer in an async loop, printing the updated status at every interval."""
        next_tick = self._start_time + self._interval
        self.update_all_targets(including_unstarted=True)

        while True:
            now = time.monotonic()
            sleep_time = max(0, next_tick - now)
            await asyncio.sleep(sleep_time)
            self.update_all_targets()
            next_tick += self._interval

    def update_all_targets(self, *, including_unstarted: bool = False) -> None:
        """Update the status bars of all targets."""
        if self._paused:
            return
        update_time = time.monotonic()
        for target in self._target_counts:
            # Only update targets that have started (some job status has changed)
            if self.target_is_started(target) or including_unstarted:
                target_update_time = self._finish_time.get(target, update_time)
                self._update_target(target_update_time, target)

    def target_is_started(self, target: str) -> bool:
        """Check whether a target has been started yet or not."""
        return bool(self._num_finished[target]) or bool(self._running[target])

    def target_is_done(self, target: str) -> bool:
        """Check whether a target is finished or not."""
        return self._num_finished[target] >= self._totals[target]

    def update_status(self, job: JobSpec, old_status: JobStatus, new_status: JobStatus) -> None:
        """Update the status printer to reflect a change in job status."""
        status_counts = self._target_counts[job.target]
        status_counts[old_status] -= 1
        if old_status == JobStatus.RUNNING:
            self._running[job.target].remove(job.full_name)
        status_counts[new_status] += 1
        if new_status == JobStatus.RUNNING:
            self._running[job.target].append(job.full_name)
        if not old_status.is_terminal and new_status.is_terminal:
            self._num_finished[job.target] += 1

        if self.target_is_done(job.target) and not self.updates_every_event:
            # Even if we have a configured print interval, we should record
            # the time at which the target finished to capture accurate end timing.
            self._finish_time[job.target] = time.monotonic()
        elif self.updates_every_event:
            self.update_all_targets()

    def _get_header(self) -> str:
        """Get the header string to use for printing the status."""
        return (
            ", ".join(
                f"{status.shorthand}: {status.name.lower().rjust(self._field_width)}"
                for status in JobStatus
            )
            + ", T: total"
        )

    def _get_target_row(self, target: str) -> str:
        """Get a formatted string with the fields for a given target row."""
        fields = []
        for status in JobStatus:
            count = self._target_counts[target][status]
            value = f"{count:0{self._field_width}d}"
            fields.append(f"{status.shorthand}: {value.rjust(len(status.name))}")
        total = f"{self._totals[target]:0{self._field_width}d}"
        fields.append(f"T: {total.rjust(5)}")
        return ", ".join(fields)

    @abstractmethod
    def _print_header(self) -> None:
        """Initialize / print the header, displaying the legend of job status meanings."""

    @abstractmethod
    def _init_target(self, target: str, _msg: str) -> None:
        """Initialize the status bar for a target."""

    @abstractmethod
    def _update_target(self, current_time: float, target: str) -> None:
        """Update the status bar for a given target."""

    def pause(self) -> None:
        """Toggle whether the status printer is paused. May make target finish times inaccurate."""
        self._paused = not self._paused
        if not self._paused and self.updates_every_event:
            self.update_all_targets()

    def stop(self) -> None:
        """Stop the status header/target printing (but keep the printer context)."""
        if self._task:
            self._task.cancel()
        if self._paused:
            self._paused = False
        self.update_all_targets(including_unstarted=True)

    def exit(self) -> None:  # noqa: B027
        """Do cleanup activities before exiting."""
