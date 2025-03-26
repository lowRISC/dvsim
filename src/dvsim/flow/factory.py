# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Factory to generate a flow config."""

from argparse import Namespace
from collections.abc import Sequence

from dvsim.config.load import load_cfg
from dvsim.flow.base import FlowCfg
from dvsim.flow.cdc import CdcCfg
from dvsim.flow.formal import FormalCfg
from dvsim.flow.lint import LintCfg
from dvsim.flow.rdc import RdcCfg
from dvsim.flow.sim import SimCfg
from dvsim.flow.syn import SynCfg
from dvsim.logging import log
from dvsim.project import ProjectMeta

FLOW_HANDLERS = {
    "cdc": CdcCfg,
    "formal": FormalCfg,
    "lint": LintCfg,
    "rdc": RdcCfg,
    "sim": SimCfg,
    "syn": SynCfg,
}


def _get_flow_handler_cls(flow: str) -> type[FlowCfg]:
    """Get a flow handler class for the given flow name.

    Args:
        flow: name of the flow

    Returns:
        Class object that can be used to instantiate a flow handler

    """
    if flow not in FLOW_HANDLERS:
        known_flows = ", ".join(FLOW_HANDLERS.keys())
        msg = (
            f'Configuration file sets "flow" to "{flow}", but '
            f"this is not a known flow (known: {known_flows})."
        )
        raise RuntimeError(
            msg,
        )

    return FLOW_HANDLERS[flow]


def make_cfg(
    project_cfg: ProjectMeta,
    select_cfgs: Sequence[str] | None,
    args: Namespace,
) -> FlowCfg:
    """Make a flow config by loading the config file at path.

    Args:
        project_cfg: metadata about the project
        select_cfgs: list of child config names to use from the primary config
        args: are the arguments passed to the CLI

    Returns:
        Instantiated FlowCfg object configured using the project's top level
        config file.

    """
    log.info("Loading primary config file: %s", project_cfg.top_cfg_path)

    # load the whole project config data
    primary_cfg = dict(
        load_cfg(
            path=project_cfg.top_cfg_path,
            path_resolution_wildcards={
                "proj_root": project_cfg.root_path,
            },
            select_cfgs=select_cfgs,
        ),
    )

    # Tool specified on CLI overrides the file based config
    if args.tool is not None:
        primary_cfg["tool"] = args.tool

    if "flow" not in primary_cfg:
        msg = 'No value for the "flow" key. Are you sure this is a dvsim configuration file?'
        raise RuntimeError(
            msg,
        )

    cls = _get_flow_handler_cls(str(primary_cfg["flow"]))

    child_flow_handlers = []
    if "cfgs" in primary_cfg:
        for child_cfg_path, child_cfg_data in primary_cfg["cfgs"].items():
            # Tool specified on CLI overrides the file based config
            if args.tool is not None:
                child_cfg_data["tool"] = args.tool

            log.info(
                "Constructing child '%s' %s flow with config: '%s'",
                child_cfg_data["name"],
                child_cfg_data["flow"],
                child_cfg_path,
            )
            child_flow_handlers.append(
                cls(
                    flow_cfg_file=child_cfg_path,
                    project_cfg=project_cfg,
                    config_data=child_cfg_data,
                    args=args,
                ),
            )

    log.info(
        "Constructing top level '%s' %s flow with config: '%s'",
        primary_cfg["name"],
        primary_cfg["flow"],
        project_cfg.top_cfg_path,
    )
    log.info("Constructing top level flow handler with %s", cls.__name__)

    return cls(
        flow_cfg_file=project_cfg.top_cfg_path,
        project_cfg=project_cfg,
        config_data=primary_cfg,
        args=args,
        child_configs=child_flow_handlers,
    )
