# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Custom Exception classes for config handling."""


class ConflictingConfigValueError(Exception):
    """Config values can not be merged as their values conflict."""

    def __init__(self, *, key: str, value: object, new_value: object) -> None:
        """Initialise the Error object.

        Args:
            key: the mapping key
            value: initial value
            new_value: the value in the other config

        """
        self.key = key
        self.value = value
        self.new_value = new_value

        super().__init__(
            f"Values {value!r} and {new_value!r} are in conflict as they cannot be merged",
        )
