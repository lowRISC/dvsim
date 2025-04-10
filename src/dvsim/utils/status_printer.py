# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job status printing during a scheduled run."""

import sys
from collections.abc import Sequence

import enlighten

from dvsim.logging import log


class StatusPrinter:
    """Dummy Status Printer class for interactive mode.

    When interactive mode is set, dvsim does not print the status. By
    instantiating this dummy class (printing nothing), outer interface stays
    same.
    """

    def __init__(self) -> None:
        """Initialise."""

    def print_header(self, msg: str) -> None:
        """Initialize / print the header bar.

        The header bar contains an introductory message such as the legend of
        what Q, D, ... mean.
        """

    def init_target(self, target: str, msg: str) -> None:
        """Initialize the status bar for each target."""

    def update_target(
        self,
        target: str,
        hms: str,
        msg: str,
        perc: float,
        running: Sequence[str],
    ) -> None:
        """Periodically update the status bar for each target.

        Args:
            hms:      Elapsed time in hh:mm:ss.
            target:   The tool flow step.
            msg:      The completion status message (set externally).
            perc:     Percentage of completion.
            running:  What jobs are currently still running.

        """

    def exit(self) -> None:
        """Do cleanup activities before exiting."""


class TtyStatusPrinter(StatusPrinter):
    """Abstraction for printing the current target status onto the console.

    Targets are ASIC tool flow steps such as build, run, cov etc. These steps
    are sequenced by the Scheduler. There may be multiple jobs running in
    parallel in each target. This class provides a mechanism to periodically
    print the completion status of each target onto the terminal. Messages
    printed by this class are rather static in nature - all the necessary
    computations of how the jobs are progressing need to be handled externally.

    The following are the 'fields' accepted by this class:
    """

    # Print elapsed time in bold.
    hms_fmt = "\x1b[1m{hms:9s}\x1b[0m"
    header_fmt = hms_fmt + " [{target:^13s}]: [{msg}]"
    status_fmt = header_fmt + " {perc:3.0f}%  {running}"

    def __init__(self) -> None:
        """Initialise printer."""
        super().__init__()

        # Once a target is complete, we no longer need to update it - we can
        # just skip it. Maintaining this here provides a way to print the status
        # one last time when it reaches 100%. It is much easier to do that here
        # than in the Scheduler class.
        self.target_done = {}

    def print_header(self, msg: str) -> None:
        """Initialize / print the header bar.

        The header bar contains an introductory message such as the legend of
        what Q, D, ... mean.
        """
        log.info(self.header_fmt.format(hms="", target="legend", msg=msg))

    def init_target(self, target: str, msg: str) -> None:
        """Initialize the status bar for each target."""
        self.target_done[target] = False

    def _trunc_running(self, running) -> str:
        """Truncate the list of running items to 30 character string."""
        return running[:28] + (running[28:] and "..")

    def update_target(
        self,
        target: str,
        hms: str,
        msg: str,
        perc: float,
        running: Sequence[str],
    ) -> None:
        """Periodically update the status bar for each target.

        Args:
            hms:      Elapsed time in hh:mm:ss.
            target:   The tool flow step.
            msg:      The completion status message (set externally).
            perc:     Percentage of completion.
            running:  What jobs are currently still running.

        """
        if self.target_done[target]:
            return

        log.info(
            self.status_fmt.format(
                hms=hms,
                target=target,
                msg=msg,
                perc=perc,
                running=self._trunc_running(running),
            ),
        )
        if perc == 100:
            self.target_done[target] = True

    def exit(self) -> None:
        """Do cleanup activities before exiting."""


class EnlightenStatusPrinter(TtyStatusPrinter):
    """Abstraction for printing status using Enlighten.

    Enlighten is a third party progress bar tool. Documentation:
    https://python-enlighten.readthedocs.io/en/stable/

    Though it offers very fancy progress bar visualization, we stick to a
    simple status bar 'pinned' to the bottom of the screen for each target
    that displays statically, a pre-prepared message. We avoid the progress bar
    visualization since it requires enlighten to perform some computations the
    Scheduler already does. It also helps keep the overhead to a minimum.

    Enlighten does not work if the output of dvsim is redirected to a file, for
    example - it needs to be attached to a TTY enabled stream.
    """

    def __init__(self) -> None:
        super().__init__()

        # Initialize the status_bars for header and the targets .
        self.manager = enlighten.get_manager()
        self.status_header = None
        self.status_target = {}

    def print_header(self, msg) -> None:
        self.status_header = self.manager.status_bar(
            status_format=self.header_fmt,
            hms="",
            target="legend",
            msg="Q: queued, D: dispatched, P: passed, F: failed, K: killed, T: total",
        )

    def init_target(self, target, msg) -> None:
        super().init_target(target, msg)
        self.status_target[target] = self.manager.status_bar(
            status_format=self.status_fmt,
            hms="",
            target=target,
            msg=msg,
            perc=0.0,
            running="",
        )

    def update_target(self, target, hms, msg, perc, running) -> None:
        if self.target_done[target]:
            return

        self.status_target[target].update(
            hms=hms,
            msg=msg,
            perc=perc,
            running=self._trunc_running(running),
        )
        if perc == 100:
            self.target_done[target] = True

    def exit(self) -> None:
        """Do cleanup activities before exiting."""
        self.status_header.close()
        for target in self.status_target:
            self.status_target[target].close()


def get_status_printer(interactive: bool) -> StatusPrinter:
    """Get the status printer.

    If stdout is a TTY, then return an instance of EnlightenStatusPrinter, else
    return an instance of StatusPrinter.
    """
    if interactive:
        return StatusPrinter()

    if sys.stdout.isatty():
        return EnlightenStatusPrinter()

    return TtyStatusPrinter()


def print_msg_list(msg_list_title, msg_list, max_msg_count=-1):
    """Print a list of messages to Markdown.

    The argument msg_list_title contains a string for the list title, whereas
    the msg_list argument contains the actual list of message strings.
    max_msg_count limits the number of messages to be printed (set to negative
    number to print all messages).

    Example:
    print_msg_list("### Tool Warnings", ["Message A", "Message B"], 10)

    """
    md_results = ""
    if msg_list:
        md_results += msg_list_title + "\n"
        md_results += "```\n"
        for k, msg in enumerate(msg_list):
            if k <= max_msg_count or max_msg_count < 0:
                md_results += msg + "\n\n"
            else:
                suppressed_count = len(msg_list) - max_msg_count
                md_results += (
                    f"Note: {suppressed_count} more messages have been suppressed "
                    f"(max_msg_count = {max_msg_count}) \n\n"
                )
                break

        md_results += "```\n"

    return md_results
