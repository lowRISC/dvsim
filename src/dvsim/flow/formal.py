# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Sequence
from pathlib import Path
from typing import cast

import hjson
from tabulate import tabulate

from dvsim.flow.one_shot import OneShotCfg
from dvsim.job.data import CompletedJobStatus
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.utils import subst_wildcards


class FormalCfg(OneShotCfg):
    """Derivative class for running formal tools."""

    flow = "formal"

    def __init__(self, flow_cfg_file, hjson_data, args, mk_config) -> None:
        # Options set from command line
        self.batch_mode_prefix = "" if args.gui else "-batch"

        super().__init__(flow_cfg_file, hjson_data, args, mk_config)
        self.header = [
            "name",
            "errors",
            "warnings",
            "proven",
            "cex",
            "undetermined",
            "covered",
            "unreachable",
            "pass_rate",
            "cov_rate",
        ]

        # Default not to publish child cfg results.
        self.publish_report = hjson_data.get("publish_report", False)
        self.sub_flow = hjson_data["sub_flow"]
        # Coverage columns read by get_coverage; empty when coverage is unavailable.
        self.cov_header: list[str] = []
        self.summary_header = ["name", "pass_rate", "formal_cov", "stimuli_cov", "checker_cov"]
        self.results_title = self.name.upper() + " Formal " + self.sub_flow.upper() + " Results"

    def parse_dict_to_str(self, input_dict, excl_keys=None):
        # This is a helper function to parse dictionary items into a string.
        # This function has an optional input "excl_keys" for user to exclude
        # printing out certain items according to their keys.
        # Note this function did not sort the input dictionary's key value
        # before printing the keys and items. If input dictionary is not an
        # OrderedDictionary, print out key order is not predictable.
        # This function works for Hjson lib outputs because the lib uses an
        # OrderDict when it reads dictionaries.
        # Example Input:
        # {
        #   "unreachable": ["prop1, prop2, prop3"],
        #   "cex"        : ["prop1"],
        # }
        # Example Output:
        # string = "unreachable:
        # ```
        # prop1
        # prop2
        # prop3
        # ```
        # cex:
        # ```
        # prop1
        # ```"
        if excl_keys is None:
            excl_keys = []
        output_str = ""
        for key, item in input_dict.items():
            if (key not in excl_keys) and item:
                output_str += "\n" + key + ":\n"
                output_str += "```\n"
                output_str += "\n".join(item)
                output_str += "\n```\n"
        return output_str

    def get_summary(self, result):
        summary = []
        formal_summary = result.get("summary")
        if formal_summary is None:
            results_str = "No summary information found\n"
            summary.append("N/A")
        else:
            colalign = ("center",) * len(self.header)
            table = [self.header]
            table.append(
                [
                    self.name,
                    str(formal_summary["errors"]) + " E ",
                    str(formal_summary["warnings"]) + " W ",
                    str(formal_summary["proven"]) + " G ",
                    str(formal_summary["cex"]) + " E ",
                    str(formal_summary["undetermined"]) + " W ",
                    str(formal_summary["covered"]) + " G ",
                    str(formal_summary["unreachable"]) + " E ",
                    formal_summary["pass_rate"],
                    formal_summary["cov_rate"],
                ],
            )
            summary.append(formal_summary["pass_rate"])
            if len(table) > 1:
                results_str = tabulate(
                    table,
                    headers="firstrow",
                    tablefmt="pipe",
                    colalign=colalign,
                )
            else:
                results_str = "No content in summary\n"
                summary.append("N/A")
        return results_str, summary

    def get_coverage(self, result):
        summary = []
        formal_coverage = result.get("coverage")
        if formal_coverage is None:
            results_str = "No coverage information found\n"
            summary = ["N/A", "N/A", "N/A"]
        else:
            # Use the column names from the tool's report.
            cov_header = list(formal_coverage)
            if not cov_header:
                # Treat an empty coverage mapping as unavailable.
                return "No coverage information found\n", ["N/A", "N/A", "N/A"]

            cov_colalign = ("center",) * len(cov_header)
            cov_table = [cov_header, [formal_coverage[name] for name in cov_header]]
            summary.extend(formal_coverage[name] for name in cov_header)
            # Store the columns for the primary cfg's summary.
            self.cov_header = list(cov_header)
            results_str = tabulate(
                cov_table,
                headers="firstrow",
                tablefmt="pipe",
                colalign=cov_colalign,
            )
        return results_str, summary

    def formal_cfgs(self) -> "Sequence[FormalCfg]":
        """Return child cfgs narrowed to FormalCfg for type checking."""
        return cast("Sequence[FormalCfg]", self.cfgs)

    def resolve_summary_header(self) -> list[str]:
        """Resolve the summary columns from child cfgs, logging any mismatch."""
        cfgs = self.formal_cfgs()
        measured = {tuple(cfg.cov_header) for cfg in cfgs if cfg.cov_header}
        if not measured:
            return self.summary_header
        if len(measured) > 1:
            log.error(
                "The cfgs of %s measured different coverage columns, %s, so one summary header "
                "cannot name them all. Reporting the columns of %s.",
                self.name,
                sorted(measured),
                cfgs[0].name,
            )
        columns = next(iter(measured)) if len(measured) == 1 else tuple(cfgs[0].cov_header)
        return ["name", "pass_rate", *(f"{name}_cov" for name in columns)]

    def gen_results_summary(self):
        # Summarize pass rates and the tool's coverage columns for all child cfgs.
        results_str = "## " + self.results_title + " (Summary)\n\n"
        results_str += "### " + self.timestamp_long + "\n"
        if self.revision:
            results_str += "### " + self.revision + "\n"
        results_str += "### Branch: " + self.branch + "\n"
        results_str += "\n"

        self.summary_header = self.resolve_summary_header()
        colalign = ("center",) * len(self.summary_header)
        table = [self.summary_header]
        # Keep missing-result rows aligned with the resolved header.
        missing = ["N/A"] * (len(self.summary_header) - 2)
        for cfg in self.formal_cfgs():
            try:
                table.append(cfg.result_summary[cfg.name])
            except KeyError as e:
                table.append([cfg.name, "ERROR", *missing])
                log.exception("cfg: %s could not find generated results_summary: %s", cfg.name, e)
        if len(table) > 1:
            self.results_summary_md = results_str + tabulate(
                table,
                headers="firstrow",
                tablefmt="pipe",
                colalign=colalign,
            )
        else:
            self.results_summary_md = results_str

        log.info("[result summary]: %s", self.results_summary_md)

        return self.results_summary_md

    def _gen_results_for_cfg(self, results: Sequence[CompletedJobStatus]) -> None:
        """Generate results.

        This function is called after the regression and looks for
        results.hjson file with aggregated results from the formal logfile.
        The hjson file is required to follow this format:
        {
          "messages": {
             "errors"      : []
             "warnings"    : []
             "cex"         : ["property1", "property2"...],
             "undetermined": [],
             "unreachable" : [],
          },

          "summary": {
             "errors"      : 0
             "warnings"    : 2
             "proven"      : 20,
             "cex"         : 5,
             "covered"     : 18,
             "undetermined": 7,
             "unreachable" : 2,
             "pass_rate"   : "90 %",
             "cover_rate"  : "90 %"
          },
        }
        The categories for property results are: proven, cex, undetermined,
        covered, and unreachable.

        If coverage was enabled then results.hjson will also have an item that
        shows formal coverage. It will have the following format:
          "coverage": {
             formal:  "90 %",
             stimuli: "90 %",
             checker: "80 %"
          }
        """
        # There should be just one job that has run for this config.
        complete_job = results[0]

        results_str = "## " + self.results_title + "\n\n"
        results_str += "### " + self.timestamp_long + "\n"
        if self.revision:
            results_str += "### " + self.revision + "\n"
        results_str += "### Branch: " + self.branch + "\n"
        results_str += "### Tool: " + self.tool.upper() + "\n"
        summary = [self.name]  # cfg summary for publish results

        assert len(self.deploy) == 1
        mode = self.deploy[0]

        if complete_job.status == JobStatus.PASSED:
            result_data = Path(
                subst_wildcards(self.build_dir, {"build_mode": mode.name}),
                "results.hjson",
            )
            try:
                with Path(result_data).open() as results_file:
                    self.result = hjson.load(results_file, use_decimal=True)
            except OSError as err:
                log.warning("%s", err)
                self.result = {
                    "messages": {
                        "errors": [f"IOError: {err}"],
                    },
                }

        results_str += "\n\n## Formal " + self.sub_flow.upper() + " Results\n"
        formal_result_str, formal_summary = self.get_summary(self.result)
        results_str += formal_result_str
        summary += formal_summary

        if self.cov:
            results_str += "\n\n## Coverage Results\n"
            results_str += (
                "### Coverage html file dir: " + self.scratch_path + "/default/formal-icarus\n\n"
            )
            cov_result_str, cov_summary = self.get_coverage(self.result)
            results_str += cov_result_str
            summary += cov_summary
        else:
            summary += ["N/A", "N/A", "N/A"]

        if complete_job.status != JobStatus.PASSED:
            results_str += "\n## List of Failures\n" + "".join(complete_job.fail_msg.message)

        messages = self.result.get("messages")
        if messages is not None:
            results_str += self.parse_dict_to_str(messages)

        self.results_md = results_str

        # Generate result summary
        self.result_summary[self.name] = summary

        return self.results_md
