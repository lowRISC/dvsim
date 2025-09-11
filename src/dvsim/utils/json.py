# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions for json."""

from collections.abc import Mapping
from json import loads

__all__ = ("decode_json",)


def decode_json(s: str) -> Mapping[str, object]:
    """Decode data as JSON."""
    return loads(s=s)
