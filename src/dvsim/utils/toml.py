# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions for toml."""

from collections.abc import Mapping

from toml import loads

__all__ = ("decode_toml",)


def decode_toml(s: str) -> Mapping[str, object]:
    """Decode data as JSON."""
    return loads(s=s)
