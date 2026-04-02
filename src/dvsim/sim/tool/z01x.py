# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""EDA tool plugin providing Z01X support to DVSim."""

from typing import TYPE_CHECKING

from dvsim.sim.tool.vcs import VCS

if TYPE_CHECKING:
    from dvsim.job.deploy import Deploy

__all__ = ("Z01X",)


class Z01X(VCS):
    """Implement Z01X tool support."""

    @staticmethod
    def set_additional_attrs(deploy: "Deploy") -> None:
        """Define any additional tool-specific attrs on the deploy object.

        Args:
            deploy: the deploy object to mutate.

        """
        # TODO: when circular import issues are resolved, this can be a check of
        # `isinstance(deploy, RunTest)` and we don't need the type ignores here.
        if deploy.target == "run":
            sim_run_opts = " ".join(opt.strip() for opt in deploy.run_opts)  # type: ignore[reportAttributeAccessIssue]
            deploy.exports.append({"sim_run_opts": sim_run_opts})
            deploy.run_opts = list(getattr(deploy.sim_cfg, "run_opts_fi_sim", ()))  # type: ignore[reportAttributeAccessIssue]
