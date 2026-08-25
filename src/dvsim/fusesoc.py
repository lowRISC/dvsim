# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""FuseSoC integration: mapping and cores-root control.

Flow configs frequently hardcode the FuseSoC arguments they pass, including
which ``--mapping`` selects the technology library to build against.  That makes
it impossible to build an existing config tree against a different library
without editing the config files, which is exactly what an out-of-tree
(e.g. partner-supplied) library needs to do.

The hjson ``overrides:`` key cannot solve this, because a primary config loads
its children before processing its own overrides, so an override written in a
wrapper config never reaches the children.  Command-line arguments do reach
them, because every child is constructed with the same ``args`` object.

This module provides the ``fusesoc`` section of the dvsim config file (see
:mod:`dvsim.config`), the parsing of the corresponding command-line arguments,
and the rewriting of an assembled FuseSoC argument list.

Both ``--fusesoc-mapping`` and ``--fusesoc-extra-cores-root`` are repeatable,
and values from the config file are applied before values from the command line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from dvsim.config import as_str_list, read_section, resolve_path
from dvsim.logging import log

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

__all__ = (
    "FuseSoCOptions",
    "MappingSpec",
    "options_from_config",
    "resolve_options",
    "rewrite_fusesoc_opts",
)


class MappingSpec(NamedTuple):
    """A ``--fusesoc-mapping`` value.

    ``old`` is the VLNV of a mapping to replace; when it is ``None`` the mapping
    is appended rather than replacing anything.
    """

    old: str | None
    new: str

    @classmethod
    def parse(cls, value: str) -> MappingSpec:
        """Parse ``[OLD=]NEW``.

        A VLNV never contains ``=``, so splitting on the first one is safe.
        """
        value = value.strip()
        if not value:
            msg = "--fusesoc-mapping: empty value"
            raise ValueError(msg)

        old, sep, new = value.partition("=")
        if not sep:
            return cls(None, old)

        if not old or not new:
            msg = f"--fusesoc-mapping: expected [OLD=]NEW, got {value!r}"
            raise ValueError(msg)

        return cls(old, new)


class FuseSoCOptions(NamedTuple):
    """The resolved FuseSoC options for a run."""

    mappings: tuple[MappingSpec, ...] = ()
    extra_cores_roots: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.mappings or self.extra_cores_roots)


#: Keys understood inside the config file's ``fusesoc`` section.
CONFIG_SECTION = "fusesoc"
CONFIG_KEYS = frozenset({"mapping", "extra_cores_root"})


def options_from_config(data: dict, path: Path) -> FuseSoCOptions:
    """Read the ``fusesoc`` section of an already-loaded dvsim config file."""
    section = read_section(data, CONFIG_SECTION, CONFIG_KEYS, path)

    mappings = tuple(
        MappingSpec.parse(m) for m in as_str_list(section, "mapping", CONFIG_SECTION, path)
    )
    roots = tuple(
        str(resolve_path(root, path.parent))
        for root in as_str_list(section, "extra_cores_root", CONFIG_SECTION, path)
    )

    return FuseSoCOptions(mappings, roots)


def resolve_options(args, data: dict, path: Path | None) -> FuseSoCOptions:  # noqa: ANN001
    """Combine config-file and command-line options, config file first."""
    from_file = options_from_config(data, path) if path is not None else FuseSoCOptions()
    if from_file:
        log.verbose("Read FuseSoC options from %s", path)

    cli_mappings = tuple(MappingSpec.parse(m) for m in getattr(args, "fusesoc_mapping", []) or [])
    cli_roots = tuple(getattr(args, "fusesoc_extra_cores_root", []) or [])

    return FuseSoCOptions(
        from_file.mappings + cli_mappings,
        from_file.extra_cores_roots + cli_roots,
    )


def _split(opts: Iterable[str]) -> list[str]:
    """Split an option list into individual tokens.

    Config files routinely put several tokens into one list entry, e.g.
    ``"--cores-root {proj_root}/hw"``.  Working on tokens keeps the rewriting
    rules below simple; the result is re-joined by the caller of the command.
    """
    return [token for entry in opts for token in str(entry).split()]


def rewrite_fusesoc_opts(
    opts: Sequence[str],
    options: FuseSoCOptions,
    context: str = "",
) -> list[str]:
    """Apply ``options`` to an assembled FuseSoC argument list.

    Placement follows FuseSoC's own argument grammar:

    * ``--cores-root`` is a global option, so it goes *before* the ``run``
      subcommand.
    * ``--mapping`` is an option of ``run``, so appended mappings go *after* it.

    Both the ``--mapping=VLNV`` and ``--mapping VLNV`` spellings are recognised
    when replacing.

    Every substitution is logged at INFO.  These options come from outside the
    project, so an unlogged one is a change to the build that leaves no trace in
    the tree; ``context`` says which config the arguments belong to.
    """
    if not options:
        return list(opts)

    tokens = _split(opts)

    try:
        run_index = tokens.index("run")
    except ValueError:
        log.warning(
            "FuseSoC options were given, but no 'run' subcommand was found in the "
            "command line %s -- leaving it unchanged.",
            " ".join(tokens),
        )
        return list(opts)

    tokens = _replace_mappings(tokens, options.mappings, context)

    # Recompute: _replace_mappings preserves length, but be explicit about it.
    run_index = tokens.index("run")

    head, tail = tokens[:run_index], tokens[run_index:]

    for root in options.extra_cores_roots:
        head += ["--cores-root", root]
        log.info("FuseSoC --cores-root added in %s: %s", context, root)

    appended = [f"--mapping={m.new}" for m in options.mappings if m.old is None]
    if appended:
        # tail[0] is "run"; insert directly after it.
        tail = [tail[0], *appended, *tail[1:]]
        for m in options.mappings:
            if m.old is None:
                log.info("FuseSoC --mapping added in %s: %s", context, m.new)

    return _dedupe_mappings(head + tail)


def _dedupe_mappings(tokens: list[str]) -> list[str]:
    """Drop repeated --mapping arguments, keeping the first of each.

    Config files often build these argument lists by appending, so the same
    mapping can legitimately appear twice before rewriting, and replacing both
    occurrences would then yield two identical mappings.  FuseSoC rejects that
    with "The following sources are in multiple mappings", even though the
    duplicate asks for exactly what the original did.
    """
    seen: set[str] = set()
    result: list[str] = []
    pending_flag = False

    for arg in tokens:
        if pending_flag:
            pending_flag = False
            if arg in seen:
                result.pop()  # also drop the "--mapping" that introduced it
                continue
            seen.add(arg)
            result.append(arg)
            continue

        if arg == "--mapping":
            pending_flag = True
            result.append(arg)
            continue

        if arg.startswith("--mapping="):
            vlnv = arg[len("--mapping=") :]
            if vlnv in seen:
                continue
            seen.add(vlnv)

        result.append(arg)

    return result


def _log_override(context: str, old: str, new: str) -> None:
    """Record a substitution of an in-tree value, at INFO so it cannot be missed."""
    log.info("FuseSoC --mapping override in %s: %s -> %s", context, old, new)


def _replace_mappings(
    tokens: list[str],
    mappings: Sequence[MappingSpec],
    context: str = "",
) -> list[str]:
    replacements = {m.old: m.new for m in mappings if m.old is not None}
    if not replacements:
        return tokens

    seen: set[str] = set()
    result: list[str] = []
    skip_next_value_of: str | None = None

    for arg in tokens:
        if skip_next_value_of is not None:
            # The previous argument was a bare "--mapping"; this one is its value.
            new = replacements.get(arg)
            if new is not None:
                seen.add(arg)
                result.append(new)
                _log_override(context, arg, new)
            else:
                result.append(arg)
            skip_next_value_of = None
            continue

        if arg == "--mapping":
            skip_next_value_of = arg
            result.append(arg)
            continue

        if arg.startswith("--mapping="):
            old = arg[len("--mapping=") :]
            new = replacements.get(old)
            if new is not None:
                seen.add(old)
                result.append(f"--mapping={new}")
                _log_override(context, old, new)
                continue

        result.append(arg)

    for old in replacements:
        if old not in seen:
            log.warning(
                "--fusesoc-mapping: no '--mapping=%s' found to replace; "
                "the mapping was left unchanged.",
                old,
            )

    return result
