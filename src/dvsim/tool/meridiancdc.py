#!/usr/bin/env python3
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Parses Meridian CDC report and dumps filtered messages in hjson format."""

import re
from contextlib import suppress
from pathlib import Path

from dvsim.linting.parser import LintParser
from dvsim.logging import log


def extract_rule_patterns(file_path: Path) -> list:
    """Parse the CDC summary table.

    Gets message totals, rule names, and corresponding severities.
    """
    rule_patterns = []
    full_file = ""
    # We will attempt read this file again in a second pass to parse out
    # the details, this error will get caught and reported.
    with suppress(OSError):
        full_file = file_path.read_text()
        msg = f"Read in {file_path.name}."
        log.info(msg)

    # extract the summary table
    summary_table = re.findall(
        r"^Summary of Policy: NEW((?:.|\n|\r\n)*)Rule Details of Policy: NEW",
        full_file,
        flags=re.MULTILINE,
    )
    if not summary_table:
        msg = f"No summary table found in {file_path.name}."
        log.warning(msg)
        return []

    category = ""
    severity = ""
    known_rule_names = {}
    # step through the table and identify rule names and their
    # category and severity
    for line in summary_table[0].split("\n"):
        if re.match(r"^POLICY\s+NEW", line):
            continue
        if re.match(r"^ GROUP\s+SDC_ENV_LINT", line):
            category = "sdc"
        elif re.match(r"^ GROUP\s+MCDC_SETUP_CHECKS", line):
            category = "setup"
        elif re.match(r"^ GROUP\s+MCDC_ANALYSIS_CHECKS", line):
            category = "cdc"
        elif re.match(r"^ GROUP\s+ERROR", line):
            severity = "error"
        elif re.match(r"^ GROUP\s+WARNING", line):
            severity = "warning"
        elif re.match(r"^ GROUP\s+INFO", line):
            severity = "info"
        elif re.match(r"^ GROUP\s+REVIEW", line):
            severity = "review"
        elif re.match(r"^  INSTANCE", line):
            # we've found a new rule. convert it to a known rule pattern
            # with the correct category and severity
            rule = re.findall(r"^  INSTANCE\s+([A-Z\_]+)\s+(\d+)\s+\d+?", line)
            name = rule[0][0]
            # a few rules produce messages with different severities but
            # the same rule labels. for simplicity, we promote messages
            # from lower severity buckets to the severity bucket where
            # this rule name has first been encountered. Since higher
            # severity messages are listed first in this summary table, it
            # is straightforward to check whether the rule name has
            # already appeared in a higher severity bucket.
            if name in known_rule_names:
                msg_group = known_rule_names[name]
                log.warning(
                    f"Rule {name} is reported in multiple severity "
                    "classes. All messages of this rule are "
                    f"promoted to {msg_group}"
                )

            else:
                msg_group = category + "_" + severity
                known_rule_names.update({name: msg_group})
                rule_patterns.append((msg_group, rf"^{name}:\s+\d+.*"))

    return rule_patterns


# Reuse the lint parser, but add more buckets.
class CdcParser(LintParser):
    """Class extends LintParser for CDC.

    Adds more bucket for CDC parsing.
    """

    def __init__(self) -> None:
        """Init bucket and severities."""
        self.buckets = {
            "flow_info": [],
            "flow_warning": [],
            "flow_error": [],
            "sdc_warning": [],
            "sdc_error": [],
            "setup_info": [],
            "setup_review": [],
            "setup_warning": [],
            "setup_error": [],
            "cdc_info": [],
            "cdc_review": [],
            "cdc_warning": [],
            "cdc_error": [],
            "waived_review": [],
            "tofix_error": [],
            # this bucket is temporary and will be removed at the end of the
            # parsing pass.
            "fusesoc-error": [],
        }
        self.severities = {
            "flow_info": "info",
            "flow_warning": "warning",
            "flow_error": "error",
            "sdc_warning": "warning",
            "sdc_error": "error",
            "setup_info": "info",
            "setup_review": "warning",
            "setup_warning": "warning",
            "setup_error": "error",
            "cdc_info": "info",
            "cdc_review": "warning",
            "cdc_warning": "warning",
            "cdc_error": "error",
            "waived_review": "warning",
            "tofix_error": "error",
        }


# TODO(#9079): this script will be removed long term once the
# parser has been merged with the Dvsim core code.
def cdc_parse_main(
    repdir: str | Path = "./",
    outfile: str | Path = "./results.hjson",
) -> int:
    """Parse MeridianCDC log and report files from a CDC run.

    Then filters the messages and creates an aggregated result .hjson
    file with CDC messages and their severities.

    Returns nonzero status if any warnings or errors are present.

    Args:
      repdir: Directory containing the 'build.log' and
      'mcdc.summary.rpt' files.
      Defaults to './'

      outfile: Path to the results Hjson file storage.
      Defaults to './results.hjson'

    """
    # catch the script we are running
    cdc_parse_script = Path(__file__).resolve()

    # cast to paths
    repdir_path = Path(repdir)
    outfile_path = Path(outfile)

    # report what we are running and from where
    log.info(f"Running {cdc_parse_script.name} from {cdc_parse_script.parent}")
    # Move old results file to avoid stale results if something goes wrong
    try:
        # .replace() will always overwrite the destination if it already exists
        outfile_path.replace(outfile_path.with_name(f"{outfile_path.name}.old"))
        log.info(f"Results file {outfile_path.name} moved to {outfile_path.name}.old")

    except OSError as err_msg:
        # This catches the case where the source file doesn"t exist
        log.info(
            f"Results file {outfile_path.name} does not exist or could not be moved: {err_msg.strerror}"
        )

    # Define warning/error patterns for each logfile
    parser_args = {}

    # Patterns for build.log
    parser_args.update(
        {
            repdir_path.joinpath("build.log"): [
                # If CDC warnings have been found, the CDC tool will exit with a
                # nonzero status code and fusesoc will always spit out an error
                # like
                #
                #    ERROR: Failed to build ip:core:name:0.1 : "make" exited with
                #    an error code
                #
                # If we found any other warnings or errors, there's no point in
                # listing this too. BUT we want to make sure we *do* see this error
                # if there are no other errors or warnings, since that shows
                # something has come unstuck. (Probably the CDC tool spat out a
                # warning that we don"t understand)
                ("fusesoc-error", r"^ERROR: Failed to build .* : 'make' exited with an error code"),
                ("flow_error", r"^FlexNet Licensing error.*"),
                ("flow_error", r"^  ERR \[.*"),
                # NOTE some warning are suppressed and written out to a
                # separate file, check the run-cdc.tcl script
                ("flow_warning", r"^  WARN \[.*"),
                ("flow_info", r"^  INFO \[.*"),
            ]
        }
    )

    # Patterns for mcdc.all.rpt
    # here we extract the waived and tofix error counts
    parser_args.update(
        {
            repdir_path.joinpath("REPORT/mcdc.all.rpt"): [
                ("waived_review", r"^.*\{-status\} \{Waived\}.*$"),
                ("tofix_error", r"^.*\{-status\} \{ToBeFixed\}.*$"),
            ]
        }
    )

    # The CDC messages are a bit more involved to parse out, since we
    # need to know the names and associated severities to do this.
    # The tool prints out an overview table in the report, which we are
    # going to parse first in order to get this information.
    # This is then used to construct the regex patterns to look for
    # in a second pass to get the actual CDC messages.
    cdc_rule_patterns = extract_rule_patterns(repdir_path.joinpath("REPORT/mcdc.new.rpt"))

    # Patterns for mcdc.new.rpt
    # NOTE: the "new" report does not include the waived violations
    parser_args.update({repdir_path.joinpath("REPORT/mcdc.new.rpt"): cdc_rule_patterns})

    # Parse logs
    parser = CdcParser()
    num_messages = parser.get_results(parser_args)

    # Write out results file
    parser.write_results_as_hjson(outfile_path)

    # return nonzero status if any warnings or errors are present
    # CDC infos do not count as failures
    if num_messages["error"] > 0 or num_messages["warning"] > 0:
        log.info("Found %d errors and %d warnings", num_messages["error"], num_messages["warning"])
    else:
        log.info("CDC log file parsed, no warnings or errors found")

    return 0
