# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions common across dvsim."""

from dvsim.utils.check import check_bool, check_int
from dvsim.utils.fs import (
    TS_FORMAT,
    TS_FORMAT_LONG,
    clean_odirs,
    mk_path,
    mk_symlink,
    rm_path,
)
from dvsim.utils.hjson import parse_hjson
from dvsim.utils.status_printer import (
    EnlightenStatusPrinter,
    StatusPrinter,
    print_msg_list,
)
from dvsim.utils.subprocess import run_cmd, run_cmd_with_timeout
from dvsim.utils.timer import Timer
from dvsim.utils.wildcards import (
    find_and_substitute_wildcards,
    subst_wildcards,
)

__all__ = (
    "TS_FORMAT",
    "TS_FORMAT_LONG",
    "EnlightenStatusPrinter",
    "StatusPrinter",
    "Timer",
    "check_bool",
    "check_int",
    "clean_odirs",
    "find_and_substitute_wildcards",
    "mk_path",
    "mk_symlink",
    "parse_hjson",
    "print_msg_list",
    "rm_path",
    "run_cmd",
    "run_cmd_with_timeout",
    "subst_wildcards",
)
