# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions for hjson."""

import sys
from collections.abc import Mapping
from pathlib import Path

from hjson import loads

from dvsim.logging import log


def decode_hjson(s: str) -> Mapping[str, object]:
    """Decode data as HJSON."""
    return loads(s=s, use_decimal=True)


def parse_hjson(hjson_file: Path | str) -> Mapping:
    """Parse hjson and return a dict."""
    log.debug("Parsing %s", hjson_file)

    try:
        return decode_hjson(s=Path(hjson_file).read_text())

    except Exception as e:
        log.fatal(
            'Failed to parse "%s" possibly due to bad path or syntax error.\n%s',
            hjson_file,
            e,
        )
        sys.exit(1)
