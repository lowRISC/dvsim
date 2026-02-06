# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job scheduler."""

import contextlib
import threading
from collections.abc import (
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
)
from signal import SIGINT, SIGTERM, signal
from types import FrameType
from typing import TYPE_CHECKING, Any

from dvsim.job.data import CompletedJobStatus, JobSpec
from dvsim.launcher.base import Launcher, LauncherBusyError, LauncherError
from dvsim.logging import log
from dvsim.utils.status_printer import get_status_printer
from dvsim.utils.timer import Timer

if TYPE_CHECKING:
    from dvsim.flow.base import FlowCfg


def total_sub_items(
    d: Mapping[str, Sequence[JobSpec]] | Mapping["FlowCfg", Sequence[JobSpec]],
) -> int:
    """Return the total number of sub items in a mapping.

    Given a dict whose key values are lists, return sum of lengths of
    these lists.
    """
    return sum(len(v) for v in d.values())


def get_next_item(arr: Sequence, index: int) -> tuple[Any, int]:
    """Perpetually get an item from a list.

    Returns the next item on the list by advancing the index by 1. If the index
    is already the last item on the list, it loops back to the start, thus
    implementing a circular list.

    Args:
        arr: subscriptable list.
        index: index of the last item returned.

    Returns:
        (item, index) if successful.

    Raises:
        IndexError if arr is empty.

    """
    index += 1
    try:
        item = arr[index]
    except IndexError:
        index = 0
        try:
            item = arr[index]
        except IndexError:
            msg = "List is empty!"
            raise IndexError(msg) from None

    return item, index


class Scheduler:
    """An object that runs one or more jobs from JobSpec items."""

    def __init__(
        self,
        items: Sequence[JobSpec],
        launcher_cls: type[Launcher],
        *,
        interactive: bool,
    ) -> None:
        """Initialise a job scheduler.

        Args:
            items: sequence of jobs to deploy.
            launcher_cls: Launcher class to use to deploy the jobs.
            interactive: launch the tools in interactive mode.

        """
        self._jobs: Mapping[str, JobSpec] = {i.full_name: i for i in items}

        # 'scheduled[target][cfg]' is a list of JobSpec object names for the chosen
        # target and cfg. As items in _scheduled are ready to be run (once
        # their dependencies pass), they are moved to the _queued list, where
        # they wait until slots are available for them to be dispatched.
        # When all items (in all cfgs) of a target are done, it is removed from
        # this dictionary.
        self._scheduled: MutableMapping[str, MutableMapping[str, MutableSequence[str]]] = {}
        self.add_to_scheduled(jobs=self._jobs)

        # Print status periodically using an external status printer.
        self._status_printer = get_status_printer(interactive)
        self._status_printer.print_header()

        # Sets of items, split up by their current state. The sets are
        # disjoint and their union equals the keys of self.item_status.
        # _queued is a list so that we dispatch things in order (relevant
        # for things like tests where we have ordered things cleverly to
        # try to see failures early). They are maintained for each target.

        # The list of available targets and the list of running items in each
        # target are polled in a circular fashion, looping back to the start.
        # This is done to allow us to poll a smaller subset of jobs rather than
        # the entire regression. We keep rotating through our list of running
        # items, picking up where we left off on the last poll.
        self._targets: Sequence[str] = list(self._scheduled.keys())
        self._total: MutableMapping[str, int] = {}

        self._queued: MutableMapping[str, MutableSequence[str]] = {}
        self._running: MutableMapping[str, MutableSequence[str]] = {}

        self._passed: MutableMapping[str, MutableSet[str]] = {}
        self._failed: MutableMapping[str, MutableSet[str]] = {}
        self._killed: MutableMapping[str, MutableSet[str]] = {}

        self._last_target_polled_idx = -1
        self._last_item_polled_idx = {}

        for target in self._scheduled:
            self._queued[target] = []
            self._running[target] = []

            self._passed[target] = set()
            self._failed[target] = set()
            self._killed[target] = set()

            self._total[target] = total_sub_items(self._scheduled[target])
            self._last_item_polled_idx[target] = -1

            # Stuff for printing the status.
            width = len(str(self._total[target]))
            field_fmt = f"{{:0{width}d}}"
            self._msg_fmt = (
                f"Q: {field_fmt}, D: {field_fmt}, P: {field_fmt}, "
                f"F: {field_fmt}, K: {field_fmt}, T: {field_fmt}"
            )
            msg = self._msg_fmt.format(0, 0, 0, 0, 0, self._total[target])
            self._status_printer.init_target(target=target, msg=msg)

        # A map from the job names tracked by this class to their
        # current status. This status is 'Q', 'D', 'P', 'F' or 'K',
        # corresponding to membership in the dicts above. This is not
        # per-target.
        self.job_status: MutableMapping[str, str] = {}

        # Create the launcher instance for all items.
        self._launchers: Mapping[str, Launcher] = {
            full_name: launcher_cls(job_spec) for full_name, job_spec in self._jobs.items()
        }

        # The chosen launcher class. This allows us to access launcher
        # variant-specific settings such as max parallel jobs & poll rate.
        self._launcher_cls: type[Launcher] = launcher_cls

    def run(self) -> Sequence[CompletedJobStatus]:
        """Run all scheduled jobs and return the results.

        Returns the results (status) of all items dispatched for all
        targets and cfgs.
        """
        timer = Timer()

        # Catch one SIGINT and tell the runner to quit. On a second, die.
        stop_now = threading.Event()
        old_handler = None

        def on_signal(signal_received: int, _: FrameType | None) -> None:
            log.info(
                "Received signal %s. Exiting gracefully.",
                signal_received,
            )

            if signal_received == SIGINT:
                log.info(
                    "Send another to force immediate quit (but you may "
                    "need to manually kill child processes)",
                )

                # Restore old handler to catch a second SIGINT
                if old_handler is None:
                    raise RuntimeError("Old SIGINT handler not found")

                signal(signal_received, old_handler)

            stop_now.set()

        old_handler = signal(SIGINT, on_signal)

        # Install the SIGTERM handler before scheduling jobs.
        signal(SIGTERM, on_signal)

        # Enqueue all items of the first target.
        self._enqueue_successors(None)

        try:
            while True:
                if stop_now.is_set():
                    # We've had an interrupt. Kill any jobs that are running.
                    self._kill()

                hms = timer.hms()
                changed = self._poll(hms) or timer.check_time()
                self._dispatch(hms)
                if changed and self._check_if_done(hms):
                    break

                # This is essentially sleep(1) to wait a second between each
                # polling loop. But we do it with a bounded wait on stop_now so
                # that we jump back to the polling loop immediately on a
                # signal.
                stop_now.wait(timeout=self._launcher_cls.poll_freq)

        finally:
            signal(SIGINT, old_handler)

        # Cleanup the status printer.
        self._status_printer.exit()

        # We got to the end without anything exploding. Return the results.
        results = []
        for name, status in self.job_status.items():
            launcher = self._launchers[name]
            job_spec = self._jobs[name]

            results.append(
                CompletedJobStatus(
                    name=job_spec.name,
                    job_type=job_spec.job_type,
                    seed=job_spec.seed,
                    block=job_spec.block,
                    tool=job_spec.tool,
                    workspace_cfg=job_spec.workspace_cfg,
                    full_name=name,
                    qual_name=job_spec.qual_name,
                    target=job_spec.target,
                    log_path=job_spec.log_path,
                    job_runtime=launcher.job_runtime.with_unit("s").get()[0],
                    simulated_time=launcher.simulated_time.with_unit("us").get()[0],
                    status=status,
                    fail_msg=launcher.fail_msg,
                )
            )

        return results

    def add_to_scheduled(self, jobs: Mapping[str, JobSpec]) -> None:
        """Add jobs to the schedule.

        Args:
            jobs: the jobs to add to the schedule.

        """
        for full_name, job_spec in jobs.items():
            target_dict = self._scheduled.setdefault(job_spec.target, {})
            cfg_list = target_dict.setdefault(job_spec.block.name, [])

            if job_spec not in cfg_list:
                cfg_list.append(full_name)

    def _unschedule_item(self, job_name: str) -> None:
        """Remove deploy item from the schedule."""
        job = self._jobs[job_name]
        target_dict = self._scheduled[job.target]
        cfg_list = target_dict.get(job.block.name)

        if cfg_list is not None:
            with contextlib.suppress(ValueError):
                cfg_list.remove(job_name)

            # When all items in _scheduled[target][cfg] are finally removed,
            # the cfg key is deleted.
            if not cfg_list:
                del target_dict[job.block.name]

    def _enqueue_successors(self, job_name: str | None = None) -> None:
        """Move an item's successors from _scheduled to _queued.

        'item' is the recently run job that has completed. If None, then we
        move all available items in all available cfgs in _scheduled's first
        target. If 'item' is specified, then we find its successors and move
        them to _queued.
        """
        for next_job_name in self._get_successors(job_name):
            target = self._jobs[next_job_name].target
            if next_job_name in self.job_status or next_job_name in self._queued[target]:
                msg = f"Job {next_job_name} already scheduled"
                raise RuntimeError(msg)

            self.job_status[next_job_name] = "Q"
            self._queued[target].append(next_job_name)
            self._unschedule_item(next_job_name)

    def _cancel_successors(self, job_name: str) -> None:
        """Cancel an item's successors.

        Recursively move them from _scheduled or _queued to _killed.

        Args:
            job_name: job whose successors are to be canceled.

        """
        items = list(self._get_successors(job_name))
        while items:
            next_item = items.pop()
            self._cancel_item(next_item, cancel_successors=False)
            items.extend(self._get_successors(next_item))

    def _get_successors(self, job_name: str | None = None) -> Sequence[str]:
        """Find immediate successors of an item.

        We choose the target that follows the 'item''s current target and find
        the list of successors whose dependency list contains 'item'. If 'item'
        is None, we pick successors from all cfgs, else we pick successors only
        from the cfg to which the item belongs.

        Args:
            job_name: name of the job

        Returns:
            list of the jobs successors, or an empty list if there are none.

        """
        if job_name is None:
            target = next(iter(self._scheduled))

            if target is None:
                return []

            cfgs = set(self._scheduled[target])

        else:
            job: JobSpec = self._jobs[job_name]

            if job.target not in self._scheduled:
                msg = f"Scheduler does not contain target {job.target}"
                raise KeyError(msg)

            target_iterator = iter(self._scheduled)
            target = next(target_iterator)

            found = False
            while not found:
                if target == job.target:
                    found = True

                try:
                    target = next(target_iterator)

                except StopIteration:
                    return []

            if target is None:
                return []

            cfgs = {job.block.name}

        # Find item's successors that can be enqueued. We assume here that
        # only the immediately succeeding target can be enqueued at this
        # time.
        successors = []
        for cfg in cfgs:
            for next_item in self._scheduled[target][cfg]:
                if job_name is not None:
                    job = self._jobs[next_item]
                    # Something is terribly wrong if item exists but the
                    # next_item's dependency list is empty.
                    assert job.dependencies
                    if job_name not in job.dependencies:
                        continue

                if self._ok_to_enqueue(next_item):
                    successors.append(next_item)

        return successors

    def _ok_to_enqueue(self, job_name: str) -> bool:
        """Check if all dependencies jobs are completed.

        Args:
            job_name: name of job.

        Returns:
            true if ALL dependencies of item are complete.

        """
        for dep in self._jobs[job_name].dependencies:
            # Ignore dependencies that were not scheduled to run.
            if dep not in self._jobs:
                continue

            # Has the dep even been enqueued?
            if dep not in self.job_status:
                return False

            # Has the dep completed?
            if self.job_status[dep] not in ["P", "F", "K"]:
                return False

        return True

    def _ok_to_run(self, job_name: str) -> bool:
        """Check if a job is ready to start.

        The item's needs_all_dependencies_passing setting is used to figure
        out whether we can run this item or not, based on its dependent jobs'
        statuses.

        Args:
            job_name: name of the job to check

        Returns:
            true if the required dependencies have passed.

        """
        job: JobSpec = self._jobs[job_name]
        # 'item' can run only if its dependencies have passed (their results
        # should already show up in the item to status map).
        for dep_name in job.dependencies:
            # Ignore dependencies that were not scheduled to run.
            if dep_name not in self._jobs:
                continue

            dep_status = self.job_status[dep_name]
            if dep_status not in ["P", "F", "K"]:
                raise ValueError("Status must be one of P, F, or K")

            if job.needs_all_dependencies_passing:
                if dep_status in ["F", "K"]:
                    return False

            elif dep_status in ["P"]:
                return True

        return job.needs_all_dependencies_passing

    def _poll(self, hms: str) -> bool:
        """Check for running items that have finished.

        Returns:
            True if something changed.

        """
        max_poll = min(
            self._launcher_cls.max_poll,
            total_sub_items(self._running),
        )

        # If there are no jobs running, we are likely done (possibly because
        # of a SIGINT). Since poll() was called anyway, signal that something
        # has indeed changed.
        if not max_poll:
            return True

        changed = False
        while max_poll:
            target, self._last_target_polled_idx = get_next_item(
                self._targets,
                self._last_target_polled_idx,
            )

            while self._running[target] and max_poll:
                max_poll -= 1
                job_name, self._last_item_polled_idx[target] = get_next_item(
                    self._running[target],
                    self._last_item_polled_idx[target],
                )
                status = self._launchers[job_name].poll()
                level = log.VERBOSE

                if status not in ["D", "P", "F", "E", "K"]:
                    msg = f"Status must be one of D, P, F, E or K but found {status}"
                    raise ValueError(msg)

                if status == "D":
                    continue

                if status == "P":
                    self._passed[target].add(job_name)

                elif status == "F":
                    self._failed[target].add(job_name)
                    level = log.ERROR

                else:
                    # Killed or Error dispatching
                    self._killed[target].add(job_name)
                    level = log.ERROR

                self._running[target].pop(self._last_item_polled_idx[target])
                self._last_item_polled_idx[target] -= 1
                self.job_status[job_name] = status

                log.log(
                    level,
                    "[%s]: [%s]: [status] [%s: %s]",
                    hms,
                    target,
                    job_name,
                    status,
                )

                # Enqueue item's successors regardless of its status.
                #
                # It may be possible that a failed item's successor may not
                # need all of its dependents to pass (if it has other dependent
                # jobs). Hence we enqueue all successors rather than canceling
                # them right here. We leave it to _dispatch() to figure out
                # whether an enqueued item can be run or not.
                self._enqueue_successors(job_name)
                changed = True

        return changed

    def _dispatch(self, hms: str) -> None:
        """Dispatch some queued items if possible."""
        slots = self._launcher_cls.max_parallel - total_sub_items(self._running)
        if slots <= 0:
            return

        # Compute how many slots to allocate to each target based on their
        # weights.
        sum_weight = 0
        slots_filled = 0
        total_weight = sum(
            self._jobs[self._queued[t][0]].weight for t in self._queued if self._queued[t]
        )

        for target in self._scheduled:
            if not self._queued[target]:
                continue

            # N slots are allocated to M targets each with W(m) weights with
            # the formula:
            #
            # N(m) = N * W(m) / T, where,
            #   T is the sum total of all weights.
            #
            # This is however, problematic due to fractions. Even after
            # rounding off to the nearest digit, slots may not be fully
            # utilized (one extra left). An alternate approach that avoids this
            # problem is as follows:
            #
            # N(m) = (N * S(W(m)) / T) - F(m), where,
            #   S(W(m)) is the running sum of weights upto current target m.
            #   F(m) is the running total of slots filled.
            #
            # The computed slots per target is nearly identical to the first
            # solution, except that it prioritizes the slot allocation to
            # targets that are earlier in the list such that in the end, all
            # slots are fully consumed.
            sum_weight += self._jobs[self._queued[target][0]].weight
            target_slots = round((slots * sum_weight) / total_weight) - slots_filled
            if target_slots <= 0:
                continue
            slots_filled += target_slots

            to_dispatch = []
            while self._queued[target] and target_slots > 0:
                next_item = self._queued[target].pop(0)
                if not self._ok_to_run(next_item):
                    self._cancel_item(next_item, cancel_successors=False)
                    self._enqueue_successors(next_item)
                    continue

                to_dispatch.append(next_item)
                target_slots -= 1

            if not to_dispatch:
                continue

            log.verbose(
                "[%s]: [%s]: [dispatch]:\n%s",
                hms,
                target,
                ", ".join(job_name for job_name in to_dispatch),
            )

            for job_name in to_dispatch:
                try:
                    self._launchers[job_name].launch()

                except LauncherError:
                    log.exception("Error launching %s", job_name)
                    self._kill_item(job_name)

                except LauncherBusyError:
                    log.exception("Launcher busy")

                    self._queued[target].append(job_name)

                    log.verbose(
                        "[%s]: [%s]: [reqeued]: %s",
                        hms,
                        target,
                        job_name,
                    )
                    continue

                self._running[target].append(job_name)
                self.job_status[job_name] = "D"

    def _kill(self) -> None:
        """Kill any running items and cancel any that are waiting."""
        # Cancel any waiting items. We take a copy of self._queued to avoid
        # iterating over the set as we modify it.
        for target in self._queued:
            for item in list(self._queued[target]):
                self._cancel_item(item)

        # Kill any running items. Again, take a copy of the set to avoid
        # modifying it while iterating over it.
        for target in self._running:
            for item in list(self._running[target]):
                self._kill_item(item)

    def _check_if_done(self, hms: str) -> bool:
        """Check if we are done executing all jobs.

        Also, prints the status of currently running jobs.
        """
        done = True
        for target in self._scheduled:
            done_cnt = sum(
                [
                    len(self._passed[target]),
                    len(self._failed[target]),
                    len(self._killed[target]),
                ],
            )
            done = done and (done_cnt == self._total[target])

            # Skip if a target has not even begun executing.
            if not (self._queued[target] or self._running[target] or done_cnt > 0):
                continue

            perc = done_cnt / self._total[target] * 100

            running = ", ".join(
                [f"{job_name}" for job_name in self._running[target]],
            )
            msg = self._msg_fmt.format(
                len(self._queued[target]),
                len(self._running[target]),
                len(self._passed[target]),
                len(self._failed[target]),
                len(self._killed[target]),
                self._total[target],
            )
            self._status_printer.update_target(
                target=target,
                msg=msg,
                hms=hms,
                perc=perc,
                running=running,
            )
        return done

    def _cancel_item(self, job_name: str, *, cancel_successors: bool = True) -> None:
        """Cancel an item and optionally all of its successors.

        Supplied item may be in _scheduled list or the _queued list. From
        either, we move it straight to _killed.

        Args:
            job_name: name of the job to cancel
            cancel_successors: if set then cancel successors as well (True).

        """
        target = self._jobs[job_name].target
        self.job_status[job_name] = "K"
        self._killed[target].add(job_name)
        if job_name in self._queued[target]:
            self._queued[target].remove(job_name)
        else:
            self._unschedule_item(job_name)

        if cancel_successors:
            self._cancel_successors(job_name)

    def _kill_item(self, job_name: str) -> None:
        """Kill a running item and cancel all of its successors.

        Args:
            job_name: name of the job to kill

        """
        target = self._jobs[job_name].target
        self._launchers[job_name].kill()
        self.job_status[job_name] = "K"
        self._killed[target].add(job_name)
        self._running[target].remove(job_name)
        self._cancel_successors(job_name)
