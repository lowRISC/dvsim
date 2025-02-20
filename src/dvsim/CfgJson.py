# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""A wrapper for loading hjson files as used by dvsim's FlowCfg."""

from dvsim.utils import parse_hjson, subst_wildcards

# A set of fields that can be overridden on the command line and shouldn't be
# loaded from the hjson in that case.
_CMDLINE_FIELDS = {"tool"}


def load_hjson(path, initial_values):
    """Load an hjson file and any includes.

    Combines them all into a single dictionary, which is then returned. This
    does wildcard substitution on include names (since it might be needed to
    find included files), but not otherwise.

    initial_values is a starting point for the dictionary to be returned (which
    is not modified). It needs to contain values for anything needed to resolve
    include files (typically, this is 'proj_root' and 'tool' (if set)).

    """
    worklist = [path]
    seen = {path}
    ret = initial_values.copy()
    is_first = True

    # Figure out a list of fields that had a value from the command line. These
    # should have been passed in as part of initial_values and we need to know
    # that we can safely ignore updates.
    arg_keys = _CMDLINE_FIELDS & initial_values.keys()

    while worklist:
        next_path = worklist.pop()
        new_paths = _load_single_file(ret, next_path, is_first, arg_keys)
        paths_seen = set(new_paths) & seen
        if paths_seen:
            msg = (
                f"The files {list(paths_seen)!r} appears more than once "
                f"when processing include {next_path!r} for {path!r}."
            )
            raise RuntimeError(
                msg,
            )
        seen |= set(new_paths)
        worklist += new_paths
        is_first = False

    return ret


def _load_single_file(target, path, is_first, arg_keys):
    """Load a single hjson file, merging its keys into target.

    Returns a list of further includes that should be loaded.

    """
    hjson = parse_hjson(path)
    if not isinstance(hjson, dict):
        msg = f"{path!r}: Top-level hjson object is not a dictionary."
        raise RuntimeError(msg)

    import_cfgs = []
    for key, dict_val in hjson.items():
        # If this key got set at the start of time and we want to ignore any
        # updates: ignore them!
        if key in arg_keys:
            continue

        # If key is 'import_cfgs', this should be a list. Add each item to the
        # list of cfgs to process
        if key == "import_cfgs":
            if not isinstance(dict_val, list):
                msg = f"{path!r}: import_cfgs value is {dict_val!r}, but should be a list."
                raise RuntimeError(
                    msg,
                )
            import_cfgs += dict_val
            continue

        # 'use_cfgs' is a bit like 'import_cfgs', but is only used for primary
        # config files (where it is a list of the child configs). This
        # shouldn't be used except at top-level (the first configuration file
        # to be loaded).
        #
        # If defined, check that it's a list, but then allow it to be set in
        # the target dictionary as usual.
        if key == "use_cfgs":
            if not is_first:
                msg = f'{path!r}: File is included by another one, but defines "use_cfgs".'
                raise RuntimeError(
                    msg,
                )
            if not isinstance(dict_val, list):
                msg = f"{path!r}: use_cfgs must be a list. Saw {dict_val!r}."
                raise RuntimeError(
                    msg,
                )

        # Otherwise, update target with this attribute
        set_target_attribute(path, target, key, dict_val)

    # Expand the names of imported configuration files as we return them
    return [
        subst_wildcards(cfg_path, target, ignored_wildcards=[], ignore_error=False)
        for cfg_path in import_cfgs
    ]


def set_target_attribute(path, target, key, dict_val) -> None:
    """Set an attribute on the target dictionary.

    This performs checks for conflicting values and merges lists /
    dictionaries.

    """
    old_val = target.get(key)
    if old_val is None:
        # A new attribute (or the old value was None, in which case it's
        # just a placeholder and needs writing). Set it and return.
        target[key] = dict_val
        return

    if isinstance(old_val, list):
        if not isinstance(dict_val, list):
            msg = (
                f"{path!r}: Conflicting types for key {key!r}: was "
                f"{old_val!r}, a list, but loaded value is {dict_val!r}, "
                f"of type {type(dict_val).__name__}."
            )
            raise RuntimeError(
                msg,
            )

        # Lists are merged by concatenation
        target[key] += dict_val
        return

    # The other types we support are "scalar" types.
    scalar_types = [(str, [""]), (int, [0, -1]), (bool, [False])]
    defaults = None
    for st_type, st_defaults in scalar_types:
        if isinstance(dict_val, st_type):
            defaults = st_defaults
            break
    if defaults is None:
        msg = f"{path!r}: Value for key {key!r} is {dict_val!r}, of unknown type {type(dict_val).__name__}."
        raise RuntimeError(
            msg,
        )
    if not isinstance(old_val, st_type):
        msg = (
            f"{path!r}: Value for key {key!r} is {dict_val!r}, but "
            f"we already had the value {old_val!r}, of an "
            "incompatible type."
        )
        raise RuntimeError(
            msg,
        )

    # The types are compatible. If the values are equal, there's nothing more
    # to do
    if old_val == dict_val:
        return

    old_is_default = old_val in defaults
    new_is_default = dict_val in defaults

    # Similarly, if new value looks like a default, ignore it (regardless
    # of whether the current value looks like a default).
    if new_is_default:
        return

    # If the existing value looks like a default and the new value doesn't,
    # take the new value.
    if old_is_default:
        target[key] = dict_val
        return

    # Neither value looks like a default. Raise an error.
    msg = (
        f"{path!r}: Value for key {key!r} is {dict_val!r}, but "
        f"we already had a conflicting value of {old_val!r}."
    )
    raise RuntimeError(
        msg,
    )
