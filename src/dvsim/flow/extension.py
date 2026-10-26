# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Cfg extensions: hjson files merged into a named flow cfg (--cfg-extend).

See the "DUT configuration" section of doc/design_doc.md.
"""

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dvsim.flow.hjson import load_hjson

__all__ = (
    "CfgExtension",
    "check_cfg_extension_overrides",
    "check_cfg_extensions_used",
    "load_cfg_extension",
    "override_names",
)


@dataclass(frozen=True)
class CfgExtension:
    """An extension file, and the name of the cfg it extends."""

    cfg_name: str
    path: Path

    @classmethod
    def parse(cls, value: str) -> "CfgExtension":
        """Parse NAME=PATH, as given to --cfg-extend.

        A relative PATH is taken from the current directory. Symlinks are
        kept, as they are in {file_dir}.
        """
        name, sep, path = value.partition("=")
        name, path = name.strip(), path.strip()
        if not sep or not name or not path:
            msg = f"Invalid cfg extension {value!r}: expected NAME=PATH."
            raise ValueError(msg)
        return cls(name, Path(os.path.normpath(Path(path).absolute())))


def load_cfg_extension(
    ext: CfgExtension, initial_values: Mapping[str, object], arg_keys: Iterable[str]
) -> dict:
    """Load an extension file and its imports.

    initial_values holds what is needed to resolve the names of imported files,
    and arg_keys those of its keys that came from the command line (as for
    load_hjson). The returned data holds only what the extension sets.

    Raises a RuntimeError if the file can't be loaded or isn't allowed.
    """
    path = str(ext.path)
    if not ext.path.is_file():
        msg = f"{path!r}: Not a file."
        raise RuntimeError(msg)

    try:
        data = load_hjson(path, initial_values, set(arg_keys))
    except SystemExit as err:
        # parse_hjson logs why a file can't be parsed and exits. Raise instead,
        # so that --on-cfg-extend-error skip can leave the extension out.
        msg = f"{path!r}: It, or a file it imports, can't be parsed (see above)."
        raise RuntimeError(msg) from err
    except ValueError as err:
        # An import_cfgs entry with a wildcard that can't be resolved.
        msg = f"{path!r}: Can't resolve the name of an imported file: {err}"
        raise RuntimeError(msg) from err

    if "use_cfgs" in data:
        msg = f"{path!r}: An extension can't set use_cfgs."
        raise RuntimeError(msg)

    # The initial values are the cfg's own. If the extension set one of them,
    # it set it to the same value (or load_hjson reported a conflict), so
    # merging it would change nothing.
    for key in initial_values:
        data.pop(key, None)

    return data


def check_cfg_extensions_used(
    extensions: Iterable[CfgExtension],
    used: Iterable[CfgExtension],
    cfg_names: Iterable[str],
    primary_name: str | None,
) -> list[str]:
    """Check that every extension was used by a loaded cfg.

    used are the extensions that some cfg matched. cfg_names are the names that
    the cfgs that can be extended had when they matched them (before any
    overrides); a primary cfg can't be extended, so its name is passed
    separately to give a clearer message. Returns a list of error messages
    (empty if all is well).
    """
    used = set(used)
    names = set(cfg_names)
    errors = []
    for ext in extensions:
        if ext in used:
            continue
        if ext.cfg_name == primary_name:
            errors.append(
                f"Cfg extension {ext.path} names the primary cfg {ext.cfg_name!r}: "
                "only a cfg that runs jobs (a child, or a cfg run on its own) can be extended."
            )
        else:
            known = ", ".join(sorted(names)) or "none"
            errors.append(
                f"Cfg extension {ext.path} names {ext.cfg_name!r}, but no loaded cfg has "
                f"that name (loaded: {known})."
            )
    return errors


def override_names(overrides: object) -> set[str]:
    """Return the names of the keys that an ``overrides`` list sets."""
    if not isinstance(overrides, list):
        return set()
    return {o["name"] for o in overrides if isinstance(o, dict) and isinstance(o.get("name"), str)}


def check_cfg_extension_overrides(overrides: object, cfg: object, taken: Iterable[str]) -> None:
    """Check an extension's overrides as the cfg will apply them.

    The cfg processes overrides only once every file is merged (see
    FlowCfg._process_overrides, whose checks these mirror). Checking an
    extension's own here, against the cfg it has just been merged into, lets
    a broken one (most often, a key that the cfg no longer has) be reported
    as that extension's fault. So an extension can only override keys that
    the cfg or an earlier extension define. taken are the keys already
    overridden before this extension.

    Raises a RuntimeError for the first problem found (its message gives the reason only).
    """
    if not isinstance(overrides, list):
        msg = "Its 'overrides' must be a list."
        raise RuntimeError(msg)
    taken = set(taken)
    for item in overrides:
        if not (isinstance(item, dict) and set(item) == {"name", "value"}):
            msg = f"Each of its overrides needs a name and a value, not {item!r}."
            raise RuntimeError(msg)
        name, value = item["name"], item["value"]
        if not isinstance(name, str):
            msg = f"Each of its overrides needs a key name, not {name!r}."
            raise RuntimeError(msg)
        if name in taken:
            msg = f"It overrides {name!r}, which is already overridden."
            raise RuntimeError(msg)
        if not hasattr(cfg, name):
            msg = f"It overrides {name!r}, which the cfg doesn't have."
            raise RuntimeError(msg)
        old = getattr(cfg, name)
        if not isinstance(value, type(old)):
            msg = (
                f"It overrides {name!r} with {value!r}, "
                f"which doesn't match the type of its value {old!r}."
            )
            raise RuntimeError(msg)
        taken.add(name)
