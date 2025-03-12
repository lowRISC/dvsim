# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions common across dvsim."""

import logging as log
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import hjson
import mistletoe
from premailer import transform

from dvsim.utils.subprocess import run_cmd, run_cmd_with_timeout
from dvsim.utils.timer import Timer
from dvsim.utils.wildcards import (
    find_and_substitute_wildcards,
    subst_wildcards,
)

__all__ = (
    "TS_FORMAT",
    "TS_FORMAT_LONG",
    "Timer",
    "check_bool",
    "check_int",
    "clean_odirs",
    "find_and_substitute_wildcards",
    "htmc_color_pc_cells",
    "md_results_to_html",
    "mk_path",
    "mk_symlink",
    "parse_hjson",
    "print_msg_list",
    "rm_path",
    "run_cmd",
    "run_cmd_with_timeout",
    "subst_wildcards",
)

# For verbose logging
VERBOSE = 15

# Timestamp format when creating directory backups.
TS_FORMAT = "%y.%m.%d_%H.%M.%S"

# Timestamp format when generating reports.
TS_FORMAT_LONG = "%A %B %d %Y %H:%M:%S UTC"


# Parse hjson and return a dict
def parse_hjson(hjson_file):
    hjson_cfg_dict = None
    try:
        log.debug("Parsing %s", hjson_file)
        f = open(hjson_file)
        text = f.read()
        hjson_cfg_dict = hjson.loads(text, use_decimal=True)
        f.close()
    except Exception as e:
        log.fatal(
            'Failed to parse "%s" possibly due to bad path or syntax error.\n%s',
            hjson_file,
            e,
        )
        sys.exit(1)
    return hjson_cfg_dict


def md_results_to_html(title: str, css_file: Path | str, md_text: str) -> str:
    """Convert results in md format to html. Add a little bit of styling."""
    html_text = "<!DOCTYPE html>\n"
    html_text += '<html lang="en">\n'
    html_text += "<head>\n"
    if title != "":
        html_text += f"  <title>{title}</title>\n"
    html_text += "</head>\n"
    html_text += "<body>\n"
    html_text += '<div class="results">\n'
    html_text += mistletoe.markdown(md_text)
    html_text += "</div>\n"
    html_text += "</body>\n"
    html_text += "</html>\n"
    html_text = htmc_color_pc_cells(html_text)
    # this function converts css style to inline html style
    return transform(html_text, external_styles=css_file, cssutils_logging_level=log.ERROR)


def htmc_color_pc_cells(text):
    """This function finds cells in a html table that contain numerical values
    (and a few known strings) followed by a single space and an identifier.
    Depending on the identifier, it shades the cell in a specific way. A set of
    12 color palettes for setting those shades are encoded in ./style.css.
    These are 'cna' (grey), 'c0' (red), 'c1' ... 'c10' (green). The shade 'cna'
    is used for items that are marked as 'not applicable'. The shades 'c1' to
    'c9' form a gradient from red to lime-green to indicate 'levels of
    completeness'. 'cna' is used for greying out a box for 'not applicable'
    items, 'c0' is for items that are considered risky (or not yet started) and
    'c10' for items that have completed successfully, or that are
    'in good standing'.

    These are the supported identifiers: %, %u, G, B, E, W, EN, WN.
    The shading behavior for these is described below.

    %:  Coloured percentage, where the number in front of the '%' sign is mapped
        to a color for the cell ranging from red ('c0') to green ('c10').
    %u: Uncoloured percentage, where no markup is applied and '%u' is replaced
        with '%' in the output.
    G:  This stands for 'Good' and results in a green cell.
    B:  This stands for 'Bad' and results in a red cell.
    E:  This stands for 'Errors' and the cell is colored with red if the number
        in front of the indicator is larger than 0. Otherwise the cell is
        colored with green.
    W:  This stands for 'Warnings' and the cell is colored with yellow ('c6')
        if the number in front of the indicator is larger than 0. Otherwise
        the cell is colored with green.
    EN: This stands for 'Errors Negative', which behaves the same as 'E' except
        that the cell is colored red if the number in front of the indicator is
        negative.
    WN: This stands for 'Warnings Negative', which behaves the same as 'W'
        except that the cell is colored yellow if the number in front of the
        indicator is negative.

    N/A items can have any of the following indicators and need not be
    preceded with a numerical value:

    '--', 'NA', 'N.A.', 'N.A', 'N/A', 'na', 'n.a.', 'n.a', 'n/a'

    """

    # Replace <td> with <td class="color-class"> based on the fp
    # value. "color-classes" are listed in ./style.css as follows: "cna"
    # for NA value, "c0" to "c10" for fp value falling between 0.00-9.99,
    # 10.00-19.99 ... 90.00-99.99, 100.0 respectively.
    def color_cell(cell, cclass, indicator="%"):
        op = cell.replace("<td", '<td class="' + cclass + '"')
        # Remove the indicator.
        return re.sub(r"\s*" + indicator + r"\s*", "", op)

    # List of 'not applicable' identifiers.
    na_list = ["--", "NA", "N.A.", "N.A", "N/A", "na", "n.a.", "n.a", "n/a"]
    na_list_patterns = "|".join(na_list)

    # List of floating point patterns: '0', '0.0' & '.0'
    fp_patterns = r"[\+\-]?\d+\.?\d*"

    patterns = fp_patterns + "|" + na_list_patterns
    indicators = "%|%u|G|B|E|W|I|EN|WN"
    match = re.findall(r"(<td.*>\s*(" + patterns + r")\s+(" + indicators + r")\s*</td>)", text)
    if len(match) > 0:
        subst_list = {}
        fp_nums = []
        for item in match:
            # item is a tuple - first is the full string indicating the table
            # cell which we want to replace, second is the floating point value.
            cell = item[0]
            fp_num = item[1]
            indicator = item[2]
            # Skip if fp_num is already processed.
            if (fp_num, indicator) in fp_nums:
                continue
            fp_nums.append((fp_num, indicator))
            if fp_num in na_list:
                subst = color_cell(cell, "cna", indicator)
            else:
                # Item is a fp num.
                try:
                    fp = float(fp_num)
                except ValueError:
                    log.exception(
                        'Percentage item "%s" in cell "%s" is not an '
                        "integer or a floating point number",
                        fp_num,
                        cell,
                    )
                    continue
                # Percentage, colored.
                if indicator == "%":
                    if fp >= 0.0 and fp < 10.0:
                        subst = color_cell(cell, "c0")
                    elif fp >= 10.0 and fp < 20.0:
                        subst = color_cell(cell, "c1")
                    elif fp >= 20.0 and fp < 30.0:
                        subst = color_cell(cell, "c2")
                    elif fp >= 30.0 and fp < 40.0:
                        subst = color_cell(cell, "c3")
                    elif fp >= 40.0 and fp < 50.0:
                        subst = color_cell(cell, "c4")
                    elif fp >= 50.0 and fp < 60.0:
                        subst = color_cell(cell, "c5")
                    elif fp >= 60.0 and fp < 70.0:
                        subst = color_cell(cell, "c6")
                    elif fp >= 70.0 and fp < 80.0:
                        subst = color_cell(cell, "c7")
                    elif fp >= 80.0 and fp < 90.0:
                        subst = color_cell(cell, "c8")
                    elif fp >= 90.0 and fp < 100.0:
                        subst = color_cell(cell, "c9")
                    elif fp >= 100.0:
                        subst = color_cell(cell, "c10")
                # Percentage, uncolored.
                elif indicator == "%u":
                    subst = cell.replace("%u", "%")
                # Good: green
                elif indicator == "G":
                    subst = color_cell(cell, "c10", indicator)
                # Bad: red
                elif indicator == "B":
                    subst = color_cell(cell, "c0", indicator)
                # Info, uncolored.
                elif indicator == "I":
                    subst = cell.replace("I", "")
                # Bad if positive: red for errors, yellow for warnings,
                # otherwise green.
                elif indicator in ["E", "W"]:
                    if fp <= 0:
                        subst = color_cell(cell, "c10", indicator)
                    elif indicator == "W":
                        subst = color_cell(cell, "c6", indicator)
                    elif indicator == "E":
                        subst = color_cell(cell, "c0", indicator)
                # Bad if negative: red for errors, yellow for warnings,
                # otherwise green.
                elif indicator in ["EN", "WN"]:
                    if fp >= 0:
                        subst = color_cell(cell, "c10", indicator)
                    elif indicator == "WN":
                        subst = color_cell(cell, "c6", indicator)
                    elif indicator == "EN":
                        subst = color_cell(cell, "c0", indicator)
            subst_list[cell] = subst
        for key, value in subst_list.items():
            text = text.replace(key, value)
    return text


def print_msg_list(msg_list_title, msg_list, max_msg_count=-1):
    """This function prints a list of messages to Markdown.

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
                md_results += "Note: %d more messages have been suppressed " % (
                    len(msg_list) - max_msg_count
                )
                md_results += "(max_msg_count = %d) \n\n" % (max_msg_count)
                break
        md_results += "```\n"
    return md_results


def rm_path(path, ignore_error=False) -> None:
    """Removes the specified path if it exists.

    'path' is a Path-like object. If it does not exist, the function simply
    returns. If 'ignore_error' is set, then exception caught by the remove
    operation is raised, else it is ignored.
    """
    exc = None
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except IsADirectoryError:
        try:
            shutil.rmtree(path)
        except OSError as e:
            exc = e
    except OSError as e:
        exc = e

    if exc:
        log.error(f"Failed to remove {path}:\n{exc}.")
        if not ignore_error:
            raise exc


def mk_path(path) -> None:
    """Create the specified path if it does not exist.

    'path' is a Path-like object. If it does exist, the function simply
    returns. If it does not exist, the function creates the path and its
    parent directories if necessary.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        log.fatal(f"Failed to create directory {path}:\n{e}.")
        sys.exit(1)


def mk_symlink(path, link) -> None:
    """Create a symlink from the given path.

    'link' is a Path-like object. If it does exist, remove the existing link and
    create a new symlink with this given path.
    If it does not exist, the function creates the symlink with the given path.
    """
    while True:
        try:
            os.symlink(path, link)
            break
        except FileExistsError:
            rm_path(link)


def clean_odirs(odir, max_odirs, ts_format=TS_FORMAT):
    """Clean previous output directories.

    When running jobs, we may want to maintain a limited history of
    previous invocations. This method finds and deletes the output
    directories at the base of input arg 'odir' with the oldest timestamps,
    if that limit is reached. It returns a list of directories that
    remain after deletion.
    """
    odir = Path(odir)

    if os.path.exists(odir):
        # If output directory exists, back it up.
        ts = datetime.fromtimestamp(os.stat(odir).st_ctime).strftime(ts_format)
        shutil.move(odir, odir.with_name(ts))

    # Get list of past output directories sorted by creation time.
    pdir = odir.resolve().parent
    if not pdir.exists():
        return []

    dirs = sorted(
        [old for old in pdir.iterdir() if (old.is_dir() and old.name != "summary")],
        key=os.path.getctime,
        reverse=True,
    )

    for old in dirs[max(0, max_odirs - 1) :]:
        shutil.rmtree(old, ignore_errors=True)

    return [] if max_odirs == 0 else dirs[: max_odirs - 1]


def check_bool(x):
    """check_bool checks if input 'x' either a bool or
    one of the following strings: ["true", "false"]
     It returns value as Bool type.
    """
    if isinstance(x, bool):
        return x

    if x.lower() not in ["true", "false"]:
        msg = f"{x} is not a boolean value."
        raise RuntimeError(msg)

    return x.lower() == "true"


def check_int(x):
    """check_int checks if input 'x' is decimal integer.
    It returns value as an int type.
    """
    if isinstance(x, int):
        return x

    if not x.isdecimal():
        msg = f"{x} is not a decimal number"
        raise RuntimeError(msg)

    return int(x)
