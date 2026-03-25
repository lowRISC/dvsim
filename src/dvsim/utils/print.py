# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Printing / CLI utilities."""


def print_msg_list(msg_list_title: str, msg_list: list[str], max_msg_count: int = -1) -> str:
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
