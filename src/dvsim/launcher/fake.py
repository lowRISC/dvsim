# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Fake Launcher that returns random results."""

from random import choice, random
from typing import TYPE_CHECKING

from dvsim.launcher.base import ErrorMessage, Launcher

if TYPE_CHECKING:
    from dvsim.job.deploy import CovReport, Deploy, RunTest


def _run_test_handler(deploy: "RunTest") -> str:
    """Handle a RunTest deploy job."""
    return choice(("P", "F"))


def _cov_report_handler(deploy: "CovReport") -> str:
    """Handle a CompileSim deploy job."""
    keys = [
        "score",
        "line",
        "cond",
        "toggle",
        "fsm",
        "branch",
        "assert",
        "group",
    ]

    deploy.cov_results_dict = {k: f"{random() * 100:.2f} %" for k in keys}

    return "P"


_DEPLOY_HANDLER = {
    "RunTest": _run_test_handler,
    "CovReport": _cov_report_handler,
}


class FakeLauncher(Launcher):
    """Launch jobs and return fake results."""

    # Poll job's completion status every this many seconds
    poll_freq = 0

    def __init__(self, deploy: "Deploy") -> None:
        """Initialize common class members."""
        super().__init__(deploy)

    def _do_launch(self) -> None:
        """Do the launch."""

    def poll(self) -> str | None:
        """Check status of the running process."""
        deploy_cls = self.deploy.__class__.__name__
        if deploy_cls in _DEPLOY_HANDLER:
            return _DEPLOY_HANDLER[deploy_cls](deploy=self.deploy)

        # Default result is Pass
        return "P"

    def kill(self) -> None:
        """Kill the running process."""
        self._post_finish(
            "K",
            ErrorMessage(line_number=None, message="Job killed!", context=[]),
        )
