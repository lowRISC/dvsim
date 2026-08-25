# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim's own configuration file.

This is distinct from the flow configs dvsim takes as its positional argument:
it configures the tool rather than describing a flow, and it is meant to be
checked in next to a project so that a workspace's settings do not have to be
repeated on every command line.

The file is hjson, the same format as the flow configs. Each feature owns a
section of it; see e.g. :mod:`dvsim.fusesoc` for the ``fusesoc`` section.
"""

from __future__ import annotations

import os
from pathlib import Path

import hjson

__all__ = (
    "CONFIG_BASENAME",
    "XDG_SUBPATH",
    "as_str_list",
    "check_top_level_keys",
    "find_config_file",
    "load_config_file",
    "proj_root_from_config",
    "read_section",
    "resolve_path",
)

#: Name of the discoverable config file. Deliberately not hidden.
CONFIG_BASENAME = "dvsim.hjson"

#: Location of the per-user config file, under $XDG_CONFIG_HOME.
XDG_SUBPATH = Path("lowRISC") / "dvsim" / CONFIG_BASENAME


def find_config_file(explicit: str | None, start_dir: Path | None = None) -> Path | None:
    """Locate the config file.

    Search order:

    1. ``explicit``, if given (an error if it does not exist),
    2. the nearest :data:`CONFIG_BASENAME` walking upwards from ``start_dir``,
    3. ``$XDG_CONFIG_HOME/lowRISC/dvsim/dvsim.hjson``.

    Walking upwards matters because dvsim is normally invoked from inside the
    project it is building, while a config file describing a workspace
    naturally lives alongside that project rather than inside it.
    """
    if explicit is not None:
        path = Path(explicit).expanduser()
        if not path.is_file():
            msg = f"dvsim config file not found: {path}"
            raise FileNotFoundError(msg)
        return path

    start = (start_dir or Path.cwd()).resolve()
    for directory in (start, *start.parents):
        candidate = directory / CONFIG_BASENAME
        if candidate.is_file():
            return candidate

    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    candidate = xdg.expanduser() / XDG_SUBPATH
    return candidate if candidate.is_file() else None


def load_config_file(path: Path) -> dict:
    """Parse a config file, returning its top-level dict."""
    try:
        data = hjson.loads(path.read_text())
    except Exception as e:
        msg = f"Failed to parse dvsim config file {path}: {e}"
        raise RuntimeError(msg) from e

    if not isinstance(data, dict):
        msg = f"dvsim config file {path} must contain a dict at the top level"
        raise RuntimeError(msg)

    return data


def read_section(data: dict, name: str, known_keys: frozenset[str], path: Path) -> dict:
    """Return one section of a config file, rejecting unknown keys.

    Rejecting rather than ignoring them turns a typo into an error at the point
    it is made, instead of a setting that silently does nothing.
    """
    section = data.get(name, {})
    if not isinstance(section, dict):
        msg = f"dvsim config file {path}: '{name}' must be a dict"
        raise RuntimeError(msg)

    unknown = set(section) - known_keys
    if unknown:
        msg = f"dvsim config file {path}: unknown key(s) in '{name}': {sorted(unknown)}"
        raise RuntimeError(msg)

    return section


def as_str_list(section: dict, key: str, name: str, path: Path) -> list[str]:
    """Read a section key that may be given as a string or a list of strings."""
    value = section.get(key, [])
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        msg = f"dvsim config file {path}: '{name}.{key}' must be a string or list of strings"
        raise RuntimeError(msg)
    return list(value)


def resolve_path(value: str, base: Path) -> Path:
    """Resolve a config-file path value against the config file's own directory.

    Absolute values are left alone.  Relative ones are taken to be relative to
    the directory holding the config file rather than to the working directory,
    so that a checked-in file means the same thing wherever dvsim is invoked
    from.
    """
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def check_top_level_keys(data: dict, known_keys: frozenset[str], path: Path) -> None:
    """Reject unknown top-level keys, so that a typo fails rather than doing nothing."""
    unknown = set(data) - known_keys
    if unknown:
        msg = f"dvsim config file {path}: unknown top-level key(s): {sorted(unknown)}"
        raise RuntimeError(msg)


def proj_root_from_config(data: dict, path: Path) -> Path | None:
    """Read the top-level ``proj_root``, resolved against the config file's directory."""
    value = data.get("proj_root")
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"dvsim config file {path}: 'proj_root' must be a string"
        raise RuntimeError(msg)
    return resolve_path(value, path.parent)
