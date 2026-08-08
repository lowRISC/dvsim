# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Class describing CDC configuration object."""

import logging
from collections.abc import Sequence

from dvsim.flow.lint import LintCfg
from dvsim.job.data import CompletedJobStatus
from dvsim.tool.meridiancdc import cdc_parse_main
from dvsim.utils import subst_wildcards

# Get the global logger definition
log = logging.getLogger(__name__)


class CdcCfg(LintCfg):
    """Derivative class from LintCfg for parsing CDC logs."""

    flow = "cdc"

    # Override the __init__ for a CDC run
    # only names at the moment
    def __init__(self, flow_cfg_file, hjson_data, args, mk_config) -> None:
        super().__init__(flow_cfg_file, hjson_data, args, mk_config)

        self.results_title = f"{self.name.upper()} CDC Results"

    # Override the _gen_results_for_cfg to generate the results.hsjon file
    # As _gen_results_for_cfg expects the results.hjson to be there
    # The results parsing is inserted before calling LintCfg _gen_results_for_cfg.
    def _gen_results_for_cfg(self, results: Sequence[CompletedJobStatus]) -> None:
        # Call the log parser for each build mode if it is not part of the build
        # Note report_cmd can be added to the meridiancdc.hjson file if a local
        # version of the parser is preferred and available.
        if self.report_cmd is None or len(self.report_cmd) == 0:
            for mode in self.build_modes:
                result_path = subst_wildcards(self.build_dir, {"build_mode": mode.name})
                result_file = f"{result_path}/results.hjson"
                cdc_parse_main(["--repdir", result_path, "--outfile", result_file])
        else:
            log.info(f"For results.hjson Using external parser: {self.report_cmd}")

        return super()._gen_results_for_cfg(results)
