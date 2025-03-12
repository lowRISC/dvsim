# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Wildcard substitution in strings within data structures.

DVSim configuration relies heavily on dynamic templating and substitutions
based on "wildcards". The helper functions in this module implement the
templating functionality in DVSim config values.
"""

import os
import re
from collections.abc import (
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
)
from pathlib import Path
from typing import TypeVar

from dvsim.utils.subprocess import run_cmd

__all__ = (
    "find_and_substitute_wildcards",
    "subst_wildcards",
)

WildcardValueType = str | bool | int | Path

T = TypeVar("T")


def _stringify_wildcard_value(*, value: WildcardValueType | Iterable[WildcardValueType]) -> str:
    """Make sense of a wildcard value as a string (see subst_wildcards).

    Strings are passed through unchanged. Integer or boolean values are printed
    as numerical strings. Lists or other sequences have their items printed
    separated by spaces.

    """
    if isinstance(value, str):
        return value

    if isinstance(value, bool | int):
        return str(int(value))

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Iterable):
        return " ".join(_stringify_wildcard_value(value=x) for x in value)

    msg = f"Wildcard had value {value!r} which is not of a supported type."
    raise ValueError(msg)


def _subst_wildcards(
    var: str,
    *,
    wildcard_values: Mapping,
    ignored_wildcards: Iterable[str],
    seen: list[str],
    ignore_error: bool = False,
) -> tuple[str, bool]:
    """Worker function for subst_wildcards.

    seen is a list of wildcards that have been expanded on the way to this call
    (used for spotting circular recursion).

    Returns (expanded, seen_err) where expanded is the new value of the string
    and seen_err is true if we stopped early because of an ignored error.

    """
    wildcard_re = re.compile(r"{([A-Za-z0-9\_]+)}")

    # Work from left to right, expanding each wildcard we find. idx is where we
    # should start searching (so that we don't keep finding a wildcard that
    # we've decided to ignore).
    idx = 0

    any_err = False

    while True:
        right_str = var[idx:]
        match = wildcard_re.search(right_str)

        # If no match, we're done.
        if match is None:
            return (var, any_err)

        name = match.group(1)

        # If the name should be ignored, skip over it.
        if name in ignored_wildcards:
            idx += match.end()
            continue

        # If the name has been seen already, we've spotted circular recursion.
        # That's not allowed!
        if name in seen:
            msg = f"String contains circular expansion of wildcard {match.group(0)!r}."
            raise ValueError(
                msg,
            )

        # Treat eval_cmd specially
        if name == "eval_cmd":
            cmd = _subst_wildcards(
                right_str[match.end() :],
                wildcard_values=wildcard_values,
                ignored_wildcards=ignored_wildcards,
                ignore_error=ignore_error,
                seen=seen,
            )[0]

            # Are there any wildcards left in cmd? If not, we can run the
            # command and we're done.
            cmd_matches = list(wildcard_re.finditer(cmd))
            if not cmd_matches:
                var = var[: match.start()] + run_cmd(cmd)
                continue

            # Otherwise, check that each of them is ignored, or that
            # ignore_error is True.
            bad_names = False
            if not ignore_error:
                bad_names = any(match.group(1) not in ignored_wildcards for match in cmd_matches)

                if bad_names:
                    msg = (
                        "Cannot run eval_cmd because the command "
                        f"expands to {cmd!r}, which still contains a "
                        "wildcard."
                    )
                    raise ValueError(
                        msg,
                    )

            # We can't run the command (because it still has wildcards), but we
            # don't want to report an error either because ignore_error is true
            # or because each wildcard that's left is ignored. Return the
            # partially evaluated version.
            return (var[:idx] + right_str[: match.end()] + cmd, True)

        # Otherwise, look up name in wildcard_values.
        value = wildcard_values.get(name)

        # If the value isn't set, check the environment
        if value is None:
            value = os.environ.get(name)

        if value is None:
            # Ignore missing values if ignore_error is True.
            if ignore_error:
                idx += match.end()
                continue

            msg = f"String to be expanded contains unknown wildcard, {match.group(0)!r}."
            raise ValueError(
                msg,
            )

        value = _stringify_wildcard_value(value=value)

        # Do any recursive expansion of value, adding name to seen (to avoid
        # circular recursion).
        value, saw_err = _subst_wildcards(
            value,
            wildcard_values=wildcard_values,
            ignored_wildcards=ignored_wildcards,
            ignore_error=ignore_error,
            seen=[*seen, name],
        )

        # Replace the original match with the result and go around again. If
        # saw_err, increment idx past what we just inserted.
        var = var[:idx] + right_str[: match.start()] + value + right_str[match.end() :]
        if saw_err:
            any_err = True
            idx += match.start() + len(value)


def subst_wildcards(
    var: str,
    wildcard_values: Mapping[str, object],
    ignored_wildcards: Iterable[str] | None = None,
    *,
    ignore_error: bool = False,
) -> str:
    """Substitute any "wildcard" variables in the string var.

    var is the string to be substituted. wildcard_values is a dictionary mapping
    variables to strings. ignored_wildcards is a list of wildcards that
    shouldn't be substituted. ignore_error means to partially evaluate rather
    than exit on an error.

    A wildcard is written as a name (alphanumeric, allowing backslash and
    underscores) surrounded by braces. For example,

      subst_wildcards('foo {x} baz', {'x': 'bar'})

    returns "foo bar baz". Dictionary values can be strings, booleans, integers
    or lists. For example:

      subst_wildcards('{a}, {b}, {c}, {d}',
                      {'a': 'a', 'b': True, 'c': 42, 'd': ['a', 10]})

    returns 'a, 1, 42, a 10'.

    If a wildcard is in ignored_wildcards, it is ignored. For example,

      subst_wildcards('{a} {b}', {'b': 'bee'}, ignored_wildcards=['a'])

    returns "{a} bee".

    If a wildcard appears in var but is not in mdict, the environment is
    checked for the variable. If the name still isn't found, the default
    behaviour is to log an error and exit. If ignore_error is True, the
    wildcard is ignored (as if it appeared in ignore_wildcards).

    If {eval_cmd} appears in the string and 'eval_cmd' is not in
    ignored_wildcards then the following text is recursively expanded. The
    result of this expansion is treated as a command to run and the text is
    replaced by the output of the command.

    If a wildcard has been ignored (either because of ignored_wildcards or
    ignore_error), the command to run in eval_cmd might contain a match for
    wildcard_re. If ignore_error is True, the command is not run. So

       subst_wildcards('{eval_cmd}{foo}', {}, ignore_error=True)

    will return '{eval_cmd}{foo}' unchanged. If ignore_error is False, the
    function logs an error and exits.

    Recursion is possible in subst_wildcards. For example,

      subst_wildcards('{a}', {'a': '{b}', 'b': 'c'})

    returns 'c'. Circular recursion is detected, however. So

      subst_wildcards('{a}', {'a': '{b}', 'b': '{a}'})

    will log an error and exit. This error is raised whether or not
    ignore_error is set.

    Since subst_wildcards works from left to right, it's possible to compute
    wildcard names with code like this:

      subst_wildcards('{a}b}', {'a': 'a {', 'b': 'bee'})

    which returns 'a bee'. This is pretty hard to read though, so is probably
    not a good idea to use.
    """
    if ignored_wildcards is None:
        ignored_wildcards = []

    return _subst_wildcards(
        var,
        wildcard_values=wildcard_values,
        ignored_wildcards=ignored_wildcards,
        ignore_error=ignore_error,
        seen=[],
    )[0]


def _subst_wildcards_in_object(
    obj: T,
    wildcard_values: Mapping,
    ignored_wildcards: Iterable,
    *,
    ignore_error: bool = False,
) -> T:
    """Recursive inplace substitute wildcards in object.

    Find wildcards in obj and substitute with values found in
    wildcard_values in-place.
    """
    if isinstance(obj, str):
        return subst_wildcards(
            var=obj,
            wildcard_values=wildcard_values,
            ignored_wildcards=ignored_wildcards,
            ignore_error=ignore_error,
        )

    if isinstance(obj, MutableMapping):
        # Recursively call this function in sub-dicts
        return _subst_wildcards_in_mapping(
            obj=obj,
            wildcard_values=wildcard_values,
            ignored_wildcards=ignored_wildcards,
            ignore_error=ignore_error,
        )

    if isinstance(obj, Sequence):
        return _subst_wildcards_in_sequence(
            obj=obj,
            wildcard_values=wildcard_values,
            ignored_wildcards=ignored_wildcards,
            ignore_error=ignore_error,
        )

    # Leave unknown object alone
    return obj


def _subst_wildcards_in_mapping(
    obj: MutableMapping,
    wildcard_values: Mapping,
    ignored_wildcards: Iterable,
    *,
    ignore_error: bool = False,
) -> Mapping:
    """Recursive substitute wildcards in MutableMapping.

    Find wildcards in dict values and substitute with values found in
    wildcard_values and return resolved dict.
    """
    for key, val in obj.items():
        obj[key] = _subst_wildcards_in_object(
            obj=val,
            wildcard_values=wildcard_values,
            ignored_wildcards=ignored_wildcards,
            ignore_error=ignore_error,
        )

    return obj


def _subst_wildcards_in_sequence(
    obj: Sequence,
    wildcard_values: Mapping,
    ignored_wildcards: Iterable,
    *,
    ignore_error: bool = False,
) -> Sequence:
    """Recursively substitute wildcards in dict.

    Find wildcards in sub_dict and substitute with values found in
    wildcard_values and return resolved sub_dict.
    """
    return [
        _subst_wildcards_in_object(
            obj[i],
            wildcard_values=wildcard_values,
            ignored_wildcards=ignored_wildcards,
            ignore_error=ignore_error,
        )
        for i in range(len(obj))
    ]


def find_and_substitute_wildcards(
    obj: T,
    wildcard_values: Mapping,
    ignored_wildcards: Iterable | None = None,
    *,
    ignore_error: bool = False,
) -> T:
    """Recursively substitute wildcards.

    Find wildcards in sub_dict and substitute with values found in
    wildcard_values and return resolved sub_dict.
    """
    if ignored_wildcards is None:
        ignored_wildcards = []

    return _subst_wildcards_in_object(
        obj=obj,
        wildcard_values=wildcard_values,
        ignored_wildcards=ignored_wildcards,
        ignore_error=ignore_error,
    )
