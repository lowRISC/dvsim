# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Helper function for loading DVSim config files.

## Formats

Load config files in several formats including HJSON, JSON, and TOML. These
formats can be extended by registering a new decoder to a file extension.

## Include other config files

Configuration files can include other configuration files by including a key
named `import_cfgs` which contains a list of paths to other config files to
import. These are resolved and recursively evaluated such that the resulting
loaded configuration dictionary is the union of all the included configuration
files. The format of included configuration files need not be the same as the
parent config file.

## Primary and Child config files

The top level or primary config file may also contain child configuration
files. These are not merged into the primary configuration, but rather
registered as a child of the primary config. Child configurations are listed in
the `use_cfgs` attribute on the primary config.

NOTE: at the moment only the top level config (primary config) can contain
child configs. Configs that contain `use_cfgs` can not be listed in another
config files `use_cfgs` attribute.

NOTE: the list of merged configurations (`import_cfgs`) is removed from the
resulting config mapping data during the load process. This is to keep the data
clean at each stage passing on only the data the next stage needs. However for
debugging purposes it could be useful to preserve the provinance of each config
value. This information is not provided by preserving the list of imported
config paths (pre wildcard substitution), as the values could be a result of
different merged files... and wildcard substitutions.
"""

from collections.abc import (
    Callable,
    Iterable,
    Mapping,
    Sequence,
)
from pathlib import Path

from dvsim.config.errors import ConflictingConfigValueError
from dvsim.logging import log
from dvsim.utils.hjson import decode_hjson

__all__ = ("load_cfg",)

_CFG_DECODERS = {
    "hjson": decode_hjson,
}


def _get_decoder(path: Path) -> Callable[[str], Mapping]:
    """Get a config decoder."""
    ext = path.suffix
    if not ext:
        log.error("Config file name '%s' requires an extension", path)
        raise ValueError

    cfg_format = ext[1:]

    if cfg_format not in _CFG_DECODERS:
        log.error(
            "Config file '%s' is of unsupported format '%s', supported formats are: %s.",
            path,
            cfg_format,
            str(list(_CFG_DECODERS.keys())),
        )
        raise TypeError

    return _CFG_DECODERS[cfg_format]


def _load_cfg_file(path: Path) -> Mapping[str, object]:
    """Load a single config file."""
    decoder = _get_decoder(path)

    data = decoder(path.read_text())

    if not data:
        msg = f"{path!r}: config file is empty"
        raise ValueError(
            msg,
        )

    if not isinstance(data, Mapping):
        msg = f"{path!r}: Top-level config object is not a dictionary."
        raise TypeError(
            msg,
        )

    return data


def _simple_path_wildcard_resolve(
    path: str,
    wildcard_values: Mapping[str, object],
) -> Path:
    """Resolve wildcards in a string path."""
    # Substitute any wildcards - only simple wildcards are supported for
    # the config file paths. So the standard library format_map is enough.
    while True:
        if "{" not in path:
            break

        try:
            path = path.format_map(wildcard_values)

        except KeyError as e:
            e.add_note(
                f"Unresolved wildcards while resolving path: {path}",
            )
            raise

    return Path(path)


def _resolve_cfg_path(
    path: Path | str,
    include_paths: Iterable[Path],
    wildcard_values: Mapping[str, object],
) -> Path:
    """Resolve a config file path.

    If the path is a string, then substitute any wildcards found in the string
    and convert to a Path object before further processing.

    If the path is a Path that exists then return the resolved version of the
    path object, converting relative paths to absolute paths. If the provided
    path is already absolute and the file it points to does not exist then
    raise a Value error. Otherwise treat the path as a relative path and look
    for the first file that exists relative to the provided include_paths.

    Args:
        path: the path to resolve
        include_paths: the provided path may be a relative path to one of these
            provided base paths.
        wildcard_values: the path may be a string containing wildcards which
            can be substituted with the values provided in this mapping.

    Returns:
        Path object that is a fully resolved path

    """
    orig_path = path
    if isinstance(path, str):
        path = _simple_path_wildcard_resolve(
            path=path,
            wildcard_values=wildcard_values,
        )

    # Resolve path relative to the provided include paths
    if not path.is_absolute():
        include_paths = list(include_paths)
        log.debug(
            "Trying to resolve as a relative path using include paths [%s]",
            ",".join(str(path) for path in include_paths),
        )

        found_path = None
        for base_path in include_paths:
            potential_path = base_path / path

            if potential_path.exists():
                found_path = potential_path
                break

        if found_path is None:
            log.error(
                "'%s' is not an absolute path, and can't find an existing file"
                "relative to the include_paths: [%s]",
                path,
                ",".join(str(path) for path in include_paths),
            )
            raise ValueError

        path = found_path

    path = path.resolve()

    log.debug("Resolved '%s' -> '%s'", orig_path, path)

    if not path.exists():
        log.error("Resolved path '%s' does not exist", path)
        raise FileNotFoundError(str(path))

    return path


def _extract_config_paths(
    data: Mapping,
    field: str,
    include_paths: Iterable[Path],
    wildcard_values: Mapping[str, object],
) -> Sequence[Path]:
    """Extract config import paths.

    Args:
        data: config data which contains both config and include paths for
              other config files.
        field: name of the field containing paths to extract and resolve
        include_paths: the provided path may be a relative path to one of these
            provided base paths.
        wildcard_values: the path may be a string containing wildcards which
            can be substituted with the values provided in this mapping.

    Returns:
        tuple containing config data and an iterable of config paths as str.
        The config paths may contain wildcards that need expanding before they
        can become valid Path objects.

    """
    if field not in data:
        return []

    import_cfgs = data[field]

    if not isinstance(import_cfgs, list):
        msg = (f"{field} is not a list of strings as expected: {import_cfgs!r}",)
        log.error(msg)
        raise TypeError(msg)

    return [
        _resolve_cfg_path(
            path=path,
            include_paths=include_paths,
            wildcard_values=wildcard_values,
        )
        for path in import_cfgs
    ]


def _merge_cfg_map(
    obj: Mapping,
    other: Mapping,
) -> Mapping[str, object]:
    """Merge configuration values from two config maps.

    This operation is recursive. Mapping types are merged where the values of
    the other config take precedent.

    Args:
        obj: initial config map
        other: config map to merge into the initial config map

    Returns:
        New map containing the merged config values.

    """
    new = dict(obj).copy()

    for k, v in other.items():
        # key doesn't exist yet, just copy the value over
        if k not in new:
            new[k] = v
            continue

        initial = new[k]

        # recursively merge maps
        if isinstance(initial, Mapping) and isinstance(v, Mapping):
            new[k] = _merge_cfg_map(initial, v)
            continue

        # merge sequence by extending the initial list with the values in the
        # other sequence
        if (
            # str is a Sequence but it should not be concatenated
            not isinstance(initial, str)
            and not isinstance(v, str)
            and isinstance(initial, Sequence)
            and isinstance(v, Sequence)
        ):
            new[k] += v
            continue

        # New value is the same as the old one, or empty
        if initial == v or not v:
            continue

        # initial value is empty so replace it with new value
        if not initial:
            new[k] = v
            continue

        raise ConflictingConfigValueError(key=k, value=initial, new_value=v)

    return new


def _merge_import_cfgs(
    top_cfg: Mapping[str, object],
    *,
    include_paths: Iterable,
    wildcard_values: Mapping,
) -> Mapping[str, object]:
    """Recursively resolve and merge import configs.

    Returns:
        mapping of config keys to values removing the 'import_cfgs' field.

    """
    import_cfgs = _extract_config_paths(
        data=top_cfg,
        field="import_cfgs",
        include_paths=include_paths,
        wildcard_values=wildcard_values,
    )

    if not import_cfgs:
        return top_cfg

    # Make the config mapping mutable so the import configs can be merged into
    # the top config.
    cfg = dict(top_cfg)

    log.verbose(
        "config directly imports:\n  - %s",
        "\n  - ".join(str(path) for path in import_cfgs),
    )

    # Take a mutable copy of the import config paths
    remaining_cfgs = list(import_cfgs)
    parsed_cfgs = set()
    while remaining_cfgs:
        next_cfg_path = remaining_cfgs.pop()

        # If already merged a config file then skip. This allows duplicate
        # imported configs, where for example a common set of definitions can
        # be included in multiple config files. Config files already parsed and
        # merged are skipped.
        if next_cfg_path in parsed_cfgs:
            continue

        parsed_cfgs.add(next_cfg_path)

        # load the imported config file
        inc_cfg = _load_cfg_file(next_cfg_path)
        cfg = _merge_cfg_map(obj=cfg, other=inc_cfg)

        inc_import_cfgs = _extract_config_paths(
            data=inc_cfg,
            field="import_cfgs",
            include_paths=include_paths,
            wildcard_values={
                **wildcard_values,
                **cfg,  # include new config values in path filename resolution
            },
        )

        # queue included configs to process
        if inc_import_cfgs:
            log.verbose(
                "config indirectly imports:\n  - %s",
                "\n  - ".join(str(path) for path in inc_import_cfgs),
            )
            remaining_cfgs.extend(inc_import_cfgs)

    # Create a filtered copy without import_cfgs key to keep the config dict
    # clean, the field has no further value.
    return {k: v for k, v in cfg.items() if k != "import_cfgs"}


def _merge_use_cfgs(
    top_cfg: Mapping[str, object],
    *,
    include_paths: Iterable,
    wildcard_values: Mapping,
    select_cfgs: Sequence[str] | None = None,
) -> Mapping[str, object]:
    """Merge in the configuration files in use_cfgs field.

    Process the list of child configuration files in use_cfgs field and store
    the resulting config data on a new `cfgs` mapping of resolved paths to
    config data.

    Returns:
        Mapping containing filtering out the 'use_cfgs' field and instead
        containing the configuration mapping data from those files in a new
        'cfgs' field.

    """
    use_cfgs = _extract_config_paths(
        data=top_cfg,
        field="use_cfgs",
        include_paths=include_paths,
        wildcard_values=wildcard_values,
    )

    if not use_cfgs:
        return top_cfg

    # Make the config mapping mutable so the import configs can be merged into
    # the top config.
    cfg = dict(top_cfg)

    cfg["cfgs"] = {
        path: load_cfg(
            path,
            include_paths=include_paths,
            path_resolution_wildcards=wildcard_values,
        )
        for path in use_cfgs
    }

    # Filter by selected configs if provided
    if select_cfgs:
        cfg["cfgs"] = {
            path: child_cfg
            for path, child_cfg in cfg["cfgs"].items()
            if child_cfg["name"] in select_cfgs
        }

    return {k: v for k, v in cfg.items() if k != "use_cfgs"}


def _apply_overrides(cfg: Mapping[str, object]) -> Mapping[str, object]:
    """Apply overrides that are found in the config."""
    if "overrides" not in cfg:
        return cfg

    overrides = cfg["overrides"]
    log.debug("applying overrides: %s", overrides)

    # copy and filter out the overrides field
    new_cfg = {k: v for k, v in cfg.items() if k != "overrides"}

    # apply the overrides
    new_cfg.update({o["name"]: o["value"] for o in overrides})

    return new_cfg


def load_cfg(
    path: Path,
    *,
    include_paths: Iterable | None = None,
    path_resolution_wildcards: Mapping | None = None,
    select_cfgs: Sequence[str] | None = None,
) -> Mapping[str, object]:
    """Load a config file and return the data.

    The config file may contain references to other config files to import.
    These are recursively loaded and merged with the initial config. The paths
    to imported configs are provided in a list of strings as the value of the
    optional `import_cfgs` key.

    Imported config paths provided may contain wildcards and may be either
    relative or absolute paths. Relative paths are resolved from the provided
    include paths in the order provided, the first path found to point to an
    existing file is used as the path to the imported config.

    Wildcards may also be included in the path strings {token} as well as any
    other string values in the configuration file. However only the wildcards
    in the paths in import_cfgs are evaluated at this stage. The other fields
    are left unchanged for downstream post processing in components that own
    the information required to resolve the wildcards.

    Once the configs referenced in import_cfgs have been merged, the
    import_cfgs key is removed.

    Args:
        path: config file to parse
        include_paths: iterable of paths to search for relative import config
            files in.
        path_resolution_wildcards: optional mapping of wildcard substitution
            values.
        select_cfgs: subset of configs to use.

    Returns:
        combined mapping of key value pairs found in the config file and its
        imported config files.

    """
    # Take an iterable but convert to list as an iterable can only be guaranteed
    # to be consumable once.
    include_paths = list(include_paths) if include_paths is not None else []

    log.verbose("Loading config file '%s'", path)

    # Load in the top level config file as is
    cfg_data = dict(
        _load_cfg_file(
            _resolve_cfg_path(
                path,
                include_paths=include_paths,
                wildcard_values={},
            ),
        ),
    )

    # Special wildcard self_dir points to the parent directory of the current
    # config. This allows config relative paths.
    cfg_data["self_dir"] = path.parent

    # config paths can be resolved with the provided wildcards, or values
    # provided in the configuration itself. However the config values used in
    # paths must be fully resolvable with constants in the config itself.
    path_resolution_wildcards = (
        {
            **path_resolution_wildcards,
            **cfg_data,
        }
        if path_resolution_wildcards is not None
        else {**cfg_data}
    )

    # Recurse the import_cfgs files and merge into the top cfg
    cfg_data = _merge_import_cfgs(
        top_cfg=cfg_data,
        include_paths=include_paths,
        wildcard_values=path_resolution_wildcards,
    )

    # Apply overrides
    cfg_data = _apply_overrides(cfg=cfg_data)

    # Import any use_cfgs child config files
    return _merge_use_cfgs(
        top_cfg=cfg_data,
        include_paths=include_paths,
        wildcard_values=path_resolution_wildcards,
        select_cfgs=select_cfgs,
    )
