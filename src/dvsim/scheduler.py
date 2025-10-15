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

from pydantic import BaseModel, ConfigDict

from dvsim.job.deploy import Deploy
from dvsim.launcher.base import ErrorMessage, Launcher, LauncherBusyError, LauncherError
from dvsim.logging import log
from dvsim.utils.status_printer import get_status_printer
from dvsim.utils.timer import Timer

if TYPE_CHECKING:
    from dvsim.flow.base import FlowCfg


class CompletedJobStatus(BaseModel):
    """Job status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    fail_msg: ErrorMessage


def total_sub_items(
    d: Mapping[str, Sequence[Deploy]] | Mapping["FlowCfg", Sequence[Deploy]],
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
    """An object that runs one or more Deploy items."""

    def __init__(
        self,
        items: Sequence[Deploy],
        launcher_cls: type[Launcher],
        *,
        interactive: bool,
    ) -> None:
        """Initialise a job scheduler."""
        self.items: Sequence[Deploy] = items

        # 'scheduled[target][cfg]' is a list of Deploy objects for the chosen
        # target and cfg. As items in _scheduled are ready to be run (once
        # their dependencies pass), they are moved to the _queued list, where
        # they wait until slots are available for them to be dispatched.
        # When all items (in all cfgs) of a target are done, it is removed from
        # this dictionary.
        self._scheduled: MutableMapping[str, MutableMapping[str, MutableSequence[Deploy]]] = {}
        self.add_to_scheduled(items)

        # Print status periodically using an external status printer.
        self.status_printer = get_status_printer(interactive)
        self.status_printer.print_header(
            msg="Q: queued, D: dispatched, P: passed, F: failed, K: killed, T: total",
        )

        # Sets of items, split up by their current state. The sets are
        # disjoint and their union equals the keys of self.item_to_status.
        # _queued is a list so that we dispatch things in order (relevant
        # for things like tests where we have ordered things cleverly to
        # try to see failures early). They are maintained for each target.

        # The list of available targets and the list of running items in each
        # target are polled in a circular fashion, looping back to the start.
        # This is done to allow us to poll a smaller subset of jobs rather than
        # the entire regression. We keep rotating through our list of running
        # items, picking up where we left off on the last poll.
        self._targets: Sequence[str] = list(self._scheduled.keys())
        self._queued: MutableMapping[str, MutableSequence[Deploy]] = {}
        self._running: MutableMapping[str, MutableSequence[Deploy]] = {}
        self._passed: MutableMapping[str, MutableSet[Deploy]] = {}
        self._failed: MutableMapping[str, MutableSet[Deploy]] = {}
        self._killed: MutableMapping[str, MutableSet[Deploy]] = {}
        self._total = {}
        self.last_target_polled_idx = -1
        self.last_item_polled_idx = {}
        for target in self._scheduled:
            self._queued[target] = []
            self._running[target] = []
            self._passed[target] = set()
            self._failed[target] = set()
            self._killed[target] = set()
            self._total[target] = total_sub_items(self._scheduled[target])
            self.last_item_polled_idx[target] = -1

            # Stuff for printing the status.
            width = len(str(self._total[target]))
            field_fmt = f"{{:0{width}d}}"
            self.msg_fmt = (
                f"Q: {field_fmt}, D: {field_fmt}, P: {field_fmt}, "
                f"F: {field_fmt}, K: {field_fmt}, T: {field_fmt}"
            )
            msg = self.msg_fmt.format(0, 0, 0, 0, 0, self._total[target])
            self.status_printer.init_target(target=target, msg=msg)

        # A map from the Deploy object names tracked by this class to their
        # current status. This status is 'Q', 'D', 'P', 'F' or 'K',
        # corresponding to membership in the dicts above. This is not
        # per-target.
        self.item_status: MutableMapping[str, str] = {}

        # Create the launcher instance for all items.
        self._launchers: Mapping[str, Launcher] = {
            item.full_name: launcher_cls(item) for item in self.items
        }

        # The chosen launcher class. This allows us to access launcher
        # variant-specific settings such as max parallel jobs & poll rate.
        self.launcher_cls: type[Launcher] = launcher_cls

    def run(self) -> Mapping[str, CompletedJobStatus]:
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
                stop_now.wait(timeout=self.launcher_cls.poll_freq)

        finally:
            signal(SIGINT, old_handler)

        # Cleanup the status printer.
        self.status_printer.exit()

        # We got to the end without anything exploding. Return the results.
        return {
            name: CompletedJobStatus(
                status=status,
                fail_msg=self._launchers[name].fail_msg,
            )
            for name, status in self.item_status.items()
        }

    def add_to_scheduled(self, items: Sequence[Deploy]) -> None:
        """Add items to the schedule.

        Args:
            items: Deploy objects to add to the schedule.

        """
        for item in items:
            target_dict = self._scheduled.setdefault(item.target, {})
            cfg_list = target_dict.setdefault(item.flow, [])
            if item not in cfg_list:
                cfg_list.append(item)

    def _unschedule_item(self, item: Deploy) -> None:
        """Remove deploy item from the schedule."""
        target_dict = self._scheduled[item.target]
        cfg_list = target_dict.get(item.flow)
        if cfg_list is not None:
            with contextlib.suppress(ValueError):
                cfg_list.remove(item)

            # When all items in _scheduled[target][cfg] are finally removed,
            # the cfg key is deleted.
            if not cfg_list:
                del target_dict[item.flow]

    def _enqueue_successors(self, item: Deploy | None = None) -> None:
        """Move an item's successors from _scheduled to _queued.

        'item' is the recently run job that has completed. If None, then we
        move all available items in all available cfgs in _scheduled's first
        target. If 'item' is specified, then we find its successors and move
        them to _queued.
        """
        for next_item in self._get_successors(item):
            assert next_item.full_name not in self.item_status
            assert next_item not in self._queued[next_item.target]
            self.item_status[next_item.full_name] = "Q"
            self._queued[next_item.target].append(next_item)
            self._unschedule_item(next_item)

    def _cancel_successors(self, item: Deploy) -> None:
        """Cancel an item's successors.

        Recursively move them from _scheduled or _queued to _killed.
        """
        items = list(self._get_successors(item))
        while items:
            next_item = items.pop()
            self._cancel_item(next_item, cancel_successors=False)
            items.extend(self._get_successors(next_item))

    def _get_successors(self, item: Deploy | None = None) -> Sequence[Deploy]:
        """Find immediate successors of an item.

        'item' is a job that has completed. We choose the target that follows
        the 'item''s current target and find the list of successors whose
        dependency list contains 'item'. If 'item' is None, we pick successors
        from all cfgs, else we pick successors only from the cfg to which the
        item belongs.

        Returns the list of item's successors, or an empty list if there are
        none.
        """
        if item is None:
            target = next(iter(self._scheduled))

            if target is None:
                return []

            cfgs = set(self._scheduled[target])

        else:
            if item.target not in self._scheduled:
                msg = f"Scheduler does not contain target {item.target}"
                raise KeyError(msg)

            target_iterator = iter(self._scheduled)
            target = next(target_iterator)

            found = False
            while not found:
                if target == item.target:
                    found = True
                try:
                    target = next(target_iterator)
                except StopIteration:
                    return []

            if target is None:
                return []

            cfgs = {item.flow}

        # Find item's successors that can be enqueued. We assume here that
        # only the immediately succeeding target can be enqueued at this
        # time.
        successors = []
        for cfg in cfgs:
            for next_item in self._scheduled[target][cfg]:
                if item is not None:
                    # Something is terribly wrong if item exists but the
                    # next_item's dependency list is empty.
                    assert next_item.dependencies
                    if item not in next_item.dependencies:
                        continue

                if self._ok_to_enqueue(next_item):
                    successors.append(next_item)

        return successors

    def _ok_to_enqueue(self, item: Deploy) -> bool:
        """Return true if ALL dependencies of item are complete."""
        for dep in item.dependencies:
            # Ignore dependencies that were not scheduled to run.
            if dep not in self.items:
                continue

            # Has the dep even been enqueued?
            if dep.full_name not in self.item_status:
                return False

            # Has the dep completed?
            if self.item_status[dep.full_name] not in ["P", "F", "K"]:
                return False

        return True

    def _ok_to_run(self, item: Deploy) -> bool:
        """Return true if the required dependencies have passed.

        The item's needs_all_dependencies_passing setting is used to figure
        out whether we can run this item or not, based on its dependent jobs'
        statuses.
        """
        # 'item' can run only if its dependencies have passed (their results
        # should already show up in the item to status map).
        for dep in item.dependencies:
            # Ignore dependencies that were not scheduled to run.
            if dep not in self.items:
                continue

            dep_status = self.item_status[dep.full_name]
            if dep_status not in ["P", "F", "K"]:
                raise ValueError("Status must be one of P, F, or K")

            if item.needs_all_dependencies_passing:
                if dep_status in ["F", "K"]:
                    return False

            elif dep_status in ["P"]:
                return True

        return item.needs_all_dependencies_passing

    def _poll(self, hms: str) -> bool:
        """Check for running items that have finished.

        Returns True if something changed.
        """
        max_poll = min(
            self.launcher_cls.max_poll,
            total_sub_items(self._running),
        )

        # If there are no jobs running, we are likely done (possibly because
        # of a SIGINT). Since poll() was called anyway, signal that something
        # has indeed changed.
        if not max_poll:
            return True

        changed = False
        while max_poll:
            target, self.last_target_polled_idx = get_next_item(
                self._targets,
                self.last_target_polled_idx,
            )

            while self._running[target] and max_poll:
                max_poll -= 1
                item, self.last_item_polled_idx[target] = get_next_item(
                    self._running[target],
                    self.last_item_polled_idx[target],
                )
                status = self._launchers[item.full_name].poll()
                level = log.VERBOSE

                if status not in ["D", "P", "F", "E", "K"]:
                    msg = f"Status must be one of D, P, F, E or K but found {status}"
                    raise ValueError(msg)

                if status == "D":
                    continue

                if status == "P":
                    self._passed[target].add(item)

                elif status == "F":
                    self._failed[target].add(item)
                    level = log.ERROR

                else:
                    # Killed or Error dispatching
                    self._killed[target].add(item)
                    level = log.ERROR

                self._running[target].pop(self.last_item_polled_idx[target])
                self.last_item_polled_idx[target] -= 1
                self.item_status[item.full_name] = status

                log.log(
                    level,
                    "[%s]: [%s]: [status] [%s: %s]",
                    hms,
                    target,
                    item.full_name,
                    status,
                )

                # Enqueue item's successors regardless of its status.
                #
                # It may be possible that a failed item's successor may not
                # need all of its dependents to pass (if it has other dependent
                # jobs). Hence we enqueue all successors rather than canceling
                # them right here. We leave it to _dispatch() to figure out
                # whether an enqueued item can be run or not.
                self._enqueue_successors(item)
                changed = True

        return changed

    def _dispatch(self, hms: str) -> None:
        """Dispatch some queued items if possible."""
        slots = self.launcher_cls.max_parallel - total_sub_items(self._running)
        if slots <= 0:
            return

        # Compute how many slots to allocate to each target based on their
        # weights.
        sum_weight = 0
        slots_filled = 0
        total_weight = sum(self._queued[t][0].weight for t in self._queued if self._queued[t])

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
            sum_weight += self._queued[target][0].weight
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
                ", ".join(item.full_name for item in to_dispatch),
            )

            for item in to_dispatch:
                try:
                    self._launchers[item.full_name].launch()

                except LauncherError:
                    log.exception("Error launching %s", item)
                    self._kill_item(item)

                except LauncherBusyError:
                    log.exception("Launcher busy")

                    self._queued[target].append(item)

                    log.verbose(
                        "[%s]: [%s]: [reqeued]: %s",
                        hms,
                        target,
                        item.full_name,
                    )
                    continue

                self._running[target].append(item)
                self.item_status[item.full_name] = "D"

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
                [f"{item.full_name}" for item in self._running[target]],
            )
            msg = self.msg_fmt.format(
                len(self._queued[target]),
                len(self._running[target]),
                len(self._passed[target]),
                len(self._failed[target]),
                len(self._killed[target]),
                self._total[target],
            )
            self.status_printer.update_target(
                target=target,
                msg=msg,
                hms=hms,
                perc=perc,
                running=running,
            )
        return done

    def _cancel_item(self, item: Deploy, *, cancel_successors: bool = True) -> None:
        """Cancel an item and optionally all of its successors.

        Supplied item may be in _scheduled list or the _queued list. From
        either, we move it straight to _killed.
        """
        self.item_status[item.full_name] = "K"
        self._killed[item.target].add(item)
        if item in self._queued[item.target]:
            self._queued[item.target].remove(item)
        else:
            self._unschedule_item(item)

        if cancel_successors:
            self._cancel_successors(item)

    def _kill_item(self, item: Deploy) -> None:
        """Kill a running item and cancel all of its successors."""
        self._launchers[item.full_name].kill()
        self.item_status[item.full_name] = "K"
        self._killed[item.target].add(item)
        self._running[item.target].remove(item)
        self._cancel_successors(item)
