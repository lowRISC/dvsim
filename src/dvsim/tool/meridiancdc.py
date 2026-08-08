#!/usr/bin/env python3
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Parses Meridian CDC report and dumps filtered messages in hjson format."""

import argparse
import logging
import re
import sys
from pathlib import Path

from dvsim.linting.parser import LintParser

# For stand alone
# Check if this file is the main entry point
IS_STANDALONE = __name__ == "__main__"
if IS_STANDALONE:
    # Get the absolute path of the directory one level up (the project root)
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    # Add it to Python's search path if it isn't already there
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


# Get the global logger definition
log = logging.getLogger(__name__)


def extract_rule_patterns(file_path: Path):
    """This parses the CDC summary table to get the message totals,
    rule names and corresponding severities.
    """
    rule_patterns = []
    full_file = ""
    try:
        with Path(file_path).open() as f:
            full_file = f.read()
    except OSError:
        # We will attempt read this file again in a second pass to parse out
        # the details, this error will get caught and reported.
        pass

    category = ""
    severity = ""
    known_rule_names = {}
    # total_msgs = 0
    # extract the summary table
    m = re.findall(
        r"^Summary of Policy: NEW((?:.|\n|\r\n)*)Rule Details of Policy: NEW",
        full_file,
        flags=re.MULTILINE,
    )
    if m:
        # step through the table and identify rule names and their
        # category and severity
        for line in m[0].split("\n"):
            if re.match(r"^POLICY\s+NEW", line):
                continue
                # total = re.findall(r"^POLICY\s+NEW\s+([0-9]+)", line)
                # total_msgs = int(total[0])
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
                # total_count = int(rule[0][1])
                # waived_count = int(rule[0][2]) if len(rule[0]) > 3 else 0
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
    def __init__(self) -> None:
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
def cdc_parse_main(args_list=None) -> int:
    parser = argparse.ArgumentParser(
        description="""This script parses MeridianCDC log and report files from
        a CDC run, filters the messages and creates an aggregated result
        .hjson file with CDC messages and their severities.

        The script returns nonzero status if any warnings or errors are
        present.
        """
    )
    parser.add_argument(
        "--repdir",
        type=lambda p: Path(p).resolve(),
        default="./",
        help="""The script searches the 'build.log' and
        'mcdc.summary.rpt' files in this directory. Defaults to './'""",
    )

    parser.add_argument(
        "--outfile",
        type=lambda p: Path(p).resolve(),
        default="./results.hjson",
        help="""Path to the results Hjson file.
        Defaults to './results.hjson'""",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print log messages to the console screen"
    )
    args = parser.parse_args(args_list)

    # catch the script we are running
    cdc_parse_script = Path(__file__).resolve()

    # report what we are running and from where
    log.info(f"Running {cdc_parse_script.name} from {cdc_parse_script.parent}")
    # Move old results file to avoid stale results if something goes wrong
    try:
        # .replace() will always overwrite the destination if it already exists
        args.outfile.replace(args.outfile.with_name(f"{args.outfile.name}.old"))
        log.info(f"Results file {args.outfile.name} moved to {args.outfile.name}.old")

    except OSError as err_msg:
        # This catches the case where the source file doesn"t exist
        log.info(
            f"Results file {args.outfile.name} does not exist or could not be moved: {err_msg.strerror}"
        )

    # Define warning/error patterns for each logfile
    parser_args = {}

    # Patterns for build.log
    parser_args.update(
        {
            args.repdir.joinpath("build.log"): [
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
            args.repdir.joinpath("REPORT/mcdc.all.rpt"): [
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
    cdc_rule_patterns = extract_rule_patterns(args.repdir.joinpath("REPORT/mcdc.new.rpt"))

    # Patterns for mcdc.new.rpt
    # NOTE: the "new" report does not include the waived violations
    parser_args.update({args.repdir.joinpath("REPORT/mcdc.new.rpt"): cdc_rule_patterns})

    # Parse logs
    parser = CdcParser()
    num_messages = parser.get_results(parser_args)

    # Write out results file
    parser.write_results_as_hjson(args.outfile)

    # return nonzero status if any warnings or errors are present
    # CDC infos do not count as failures
    if num_messages["error"] > 0 or num_messages["warning"] > 0:
        log.info("Found %d errors and %d warnings", num_messages["error"], num_messages["warning"])
        if IS_STANDALONE:
            sys.exit(1)
    else:
        log.info("CDC log file parsed, no warnings or errors found")

    if IS_STANDALONE:
        sys.exit(0)
    else:
        return 0


if __name__ == "__main__":
    # Configure Logging log to console if running stand alone
    # logging format layout
    log_layout = "[%(levelname).1s %(asctime)s %(filename)s:%(lineno)d] %(message)s"
    time_layout = "%y%m%d %H:%M:%S"
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(f"{log_layout}", datefmt=time_layout))
    active_handlers = [console_handler]

    logging.basicConfig(level=logging.INFO, handlers=active_handlers)

    cdc_parse_main()
