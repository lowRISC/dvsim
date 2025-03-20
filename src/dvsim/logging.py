# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Logging config."""

import logging as log

__all__ = (
    "VERBOSE",
    "configure_logging",
)

# Log level for verbose logging between INFO (10) and DEBUG (20)
VERBOSE = 15


def configure_logging(*, verbose: bool, debug: bool) -> None:
    """Configure the Logger."""
    # Add log level 'VERBOSE' between INFO and DEBUG
    log.addLevelName(VERBOSE, "VERBOSE")

    log_format = "%(levelname)s: [%(module)s] %(message)s"

    log_level = log.INFO
    if debug:
        log_level = log.DEBUG
    elif verbose:
        log_level = VERBOSE

    log.basicConfig(format=log_format, level=log_level)
