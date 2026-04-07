# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job status printing during a scheduled run."""

import asyncio
import os
import shutil
import sys
import termios
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from typing import ClassVar

import enlighten

from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.utils import TS_HMS_FORMAT


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
            self.update_all_targets(including_unstarted=True)
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """Run a timer in an async loop, printing the updated status at every interval."""
        next_tick = self._start_time + self._interval

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


class TtyStatusPrinter(StatusPrinter):
    """Prints the current scheduler target status onto the console / TTY via logging."""

    hms_fmt = "\x1b[1m{hms:9s}\x1b[0m"
    header_fmt = hms_fmt + " [{target:^13s}]: [{msg}]"
    status_fmt = header_fmt + " {percent:3.0f}%  {running}"

    def __init__(self, jobs: Sequence[JobSpec]) -> None:
        """Initialise the TtyStatusPrinter."""
        super().__init__(jobs)

        # Maintain a mapping of completed targets, so we only print the status one last
        # time when it reaches 100% for a target.
        self._target_done: dict[str, bool] = {}

    def _print_header(self) -> None:
        """Initialize / print the header, displaying the legend of job status meanings."""
        log.info(self.header_fmt.format(hms="", target="legend", msg=self._get_header()))

    def _init_target(self, target: str, _msg: str) -> None:
        """Initialize the status bar for a target."""
        self._target_done[target] = False

    def _trunc_running(self, running: str, width: int = 30) -> str:
        """Truncate the list of running items to a specified length."""
        if len(running) <= width:
            return running
        return running[: width - 3] + "..."

    def _update_target(self, current_time: float, target: str) -> None:
        """Update the status bar for a given target."""
        if self._target_done[target]:
            return
        if self.target_is_done(target):
            self._target_done[target] = True

        status_counts = self._target_counts[target]
        done_count = sum(status_counts[status] for status in JobStatus if status.is_terminal)
        percent = (done_count / self._totals[target] * 100) if self._totals[target] else 100
        elapsed_time = time.gmtime(current_time - self._start_time)

        log.info(
            self.status_fmt.format(
                hms=time.strftime(TS_HMS_FORMAT, elapsed_time),
                target=target,
                msg=self._get_target_row(target),
                percent=percent,
                running=self._trunc_running(", ".join(self._running[target])),
            ),
        )


class EnlightenStatusPrinter(TtyStatusPrinter):
    """Prints the current scheduler target status to the terminal using Enlighten.

    Enlighten is a third party progress bar tool. Documentation:
    https://python-enlighten.readthedocs.io/en/stable/

    Enlighten does not work if the output of DVSim is redirected to a file, for
    example - it needs to be attached to a TTY enabled stream.
    """

    # Enlighten uses a min_delta of 0.1 by default, only updating every 0.1 seconds.
    DEFAULT_MIN_DELTA = 0.1

    status_fmt_no_running = TtyStatusPrinter.status_fmt.removesuffix("{running}")
    status_fmt = "{status_msg}{running}"

    def __init__(self, jobs: Sequence[JobSpec]) -> None:
        """Initialise the EnlightenStatusPrinter."""
        super().__init__(jobs)
        if self._interval < self.DEFAULT_MIN_DELTA:
            # TODO: maybe "debounce" the updates with a delayed async refresh task?
            log.warning(
                "Configured print interval %g will not accurately reflect for %s,"
                " which uses status bars with a configured min_delta of %g by default.",
                self._interval,
                self.__class__.__name__,
                self.DEFAULT_MIN_DELTA,
            )

        # Initialize the enlighten manager and needed state
        self._manager = enlighten.get_manager()
        self._status_header: enlighten.StatusBar | None = None
        self._status_bars: dict[str, enlighten.StatusBar] = {}
        self._stopped = False

    def _print_header(self) -> None:
        """Initialize / print the header, displaying the legend of job status meanings."""
        self._status_header = self._manager.status_bar(
            status_format=self.header_fmt,
            hms="",
            target="legend",
            msg=self._get_header(),
        )

    def _init_target(self, target: str, msg: str) -> None:
        """Initialize the status bar for a target."""
        super()._init_target(target, msg)
        hms = time.strftime(TS_HMS_FORMAT, time.gmtime(0))
        msg = self.status_fmt_no_running.format(hms=hms, target=target, msg=msg, percent=0.0)
        self._status_bars[target] = self._manager.status_bar(
            status_format=self.status_fmt,
            status_msg=msg,
            running="",
        )

    def _trunc_running_to_terminal(self, running: str, offset: int) -> str:
        """Truncate the list of running items to match the max terminal width."""
        cols = shutil.get_terminal_size(fallback=(80, 24)).columns
        width = max(30, cols - offset - 1)
        return self._trunc_running(running, width)

    def _update_target(self, current_time: float, target: str) -> None:
        """Update the status bar for a given target."""
        if self._target_done[target]:
            return

        status_counts = self._target_counts[target]
        done_count = sum(status_counts[status] for status in JobStatus if status.is_terminal)
        percent = (done_count / self._totals[target] * 100) if self._totals[target] else 100
        elapsed_time = time.gmtime(current_time - self._start_time)

        status_msg = self.status_fmt_no_running.format(
            hms=time.strftime(TS_HMS_FORMAT, elapsed_time),
            target=target,
            msg=self._get_target_row(target),
            percent=percent,
        )
        offset = len(status_msg)
        running = self._trunc_running_to_terminal(", ".join(self._running[target]), offset)

        self._status_bars[target].update(status_msg=status_msg, running=running)

        if self.target_is_done(target):
            self._target_done[target] = True
            self._status_bars[target].refresh()

    def stop(self) -> None:
        """Stop the status header/target printing (but keep the printer context)."""
        super().stop()
        if self._status_header is not None:
            self._status_header.close()
        for status_bar in self._status_bars.values():
            status_bar.close()
        self._stopped = True

    def exit(self) -> None:
        """Do cleanup activities before exiting (closing the manager context)."""
        super().exit()
        if not self._stopped:
            self.stop()
        self._manager.stop()

        # Sometimes, exiting via a signal (e.g. Ctrl-C) can cause Enlighten to leave the
        # terminal in some non-raw mode. Just in case, restore regular operation.
        self._restore_terminal()

    def _restore_terminal(self) -> None:
        """Restore regular terminal operation after using Enlighten."""
        # Try open /dev/tty, otherwise fallback to sys.stdin
        try:
            fd = os.open("/dev/tty", os.O_RDWR)
            close_fd = True
        except (OSError, termios.error):
            fd = sys.stdin.fileno()
            close_fd = False

        # By default, the terminal should echo input (ECHO) and run in canonical mode (ICANON).
        # We make this change after all buffered output is transmitted (TCSADRAIN).
        try:
            attrs = termios.tcgetattr(fd)
            attrs[3] |= termios.ECHO | termios.ICANON
            termios.tcsetattr(fd, termios.TCSADRAIN, attrs)
        except termios.error:
            log.debug("Unable to restore terminal attributes safely")

        if close_fd:
            os.close(fd)


class StatusPrinterSingleton:
    """Singleton for the status printer to uniquely refer to 1 instance at a time."""

    _instance: ClassVar[StatusPrinter | None] = None

    @classmethod
    def set(cls, instance: StatusPrinter | None) -> None:
        """Set the stored status printer."""
        cls._instance = instance

    @classmethod
    def get(cls) -> StatusPrinter | None:
        """Get the stored status printer (if it exists)."""
        return cls._instance


def create_status_printer(jobs: Sequence[JobSpec]) -> StatusPrinter:
    """Create the global status printer.

    If stdout is a TTY, then return an instance of EnlightenStatusPrinter, else
    return an instance of StatusPrinter.
    """
    status_printer = StatusPrinterSingleton.get()
    if status_printer is not None:
        return status_printer

    status_printer = EnlightenStatusPrinter(jobs) if sys.stdout.isatty() else TtyStatusPrinter(jobs)
    StatusPrinterSingleton.set(status_printer)
    return status_printer


def get_status_printer() -> StatusPrinter:
    """Retrieve the configured global status printer."""
    status_printer = StatusPrinterSingleton.get()
    if status_printer is None:
        raise RuntimeError("get_status_printer called without first creating the status printer")
    return status_printer
