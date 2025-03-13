# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions common across dvsim."""

import logging as log
import re
from pathlib import Path

import mistletoe
from premailer import transform

__all__ = (
    "htmc_color_pc_cells",
    "md_results_to_html",
)


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
    return transform(
        html_text,
        css_text=Path(css_file).read_text(),
        cssutils_logging_level=log.ERROR,
    )


def htmc_color_pc_cells(text: str) -> str:
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

    %:  Coloured percentage, where the number in front of the '%' sign is
        mapped to a color for the cell ranging from red ('c0') to
        green ('c10').
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
    proceeded with a numerical value:

    '--', 'NA', 'N.A.', 'N.A', 'N/A', 'na', 'n.a.', 'n.a', 'n/a'

    """

    # Replace <td> with <td class="color-class"> based on the fp
    # value. "color-classes" are listed in ./style.css as follows: "cna"
    # for NA value, "c0" to "c10" for fp value falling between 0.00-9.99,
    # 10.00-19.99 ... 90.00-99.99, 100.0 respetively.
    def color_cell(cell: str, cclass: str, indicator: str = "%") -> str:
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
    match = re.findall(
        r"(<td.*>\s*(" + patterns + r")\s+(" + indicators + r")\s*</td>)",
        text,
    )

    if len(match) > 0:
        subst_list = {}
        fp_nums = []

        for item in match:
            # item is a tuple - first is the full string indicating the table
            # cell which we want to replace, second is the floating point
            # value.
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
                if indicator == "%" and fp >= 0.0:
                    color_bin = min(int(fp // 10), 10)
                    subst = color_cell(cell, f"c{color_bin}")

                # Percentage, uncolored.
                elif indicator == "%u":
                    subst = cell.replace("%u", "%")

                # Good - green
                elif indicator == "G":
                    subst = color_cell(cell, "c10", indicator)

                # Bad - red
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
