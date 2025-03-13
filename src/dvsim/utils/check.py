# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Utility functions common across dvsim."""

__all__ = (
    "check_bool",
    "check_int",
)


def check_bool(x: bool | str) -> bool:
    """Check str bool representation.

    If input 'x' either a bool or
    one of the following strings: ["true", "false"]
    It returns value as Bool type.
    """
    if isinstance(x, bool):
        return x

    x = x.lower()
    if x not in ("true", "false"):
        msg = f"'{x}' is not a boolean value."
        raise RuntimeError(msg)

    return x == "true"


def check_int(x: int | object) -> int:
    """Check if x is an integer.

    If input 'x' is decimal integer. It returns value as an int type.
    """
    if isinstance(x, int):
        return x

    if not x.isdecimal():
        msg = f"{x} is not a decimal number"
        raise RuntimeError(msg)

    return int(x)
