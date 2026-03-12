# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Reporting artifacts."""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeAlias

from dvsim.templates.render import render_static

__all__ = (
    "ReportArtifacts",
    "display_report",
    "render_static_content",
    "write_report",
)

# Report rendering returns mappings of relative report paths to (string) contents.
ReportArtifacts: TypeAlias = dict[str, str]


def write_report(files: ReportArtifacts, root: Path) -> None:
    """Write rendered report artifacts to the file system, relative to a given path.

    Args:
        files: the output report artifacts from rendering simulation results.
        root: the path to write the report files relative to.

    """
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def display_report(
    files: ReportArtifacts, sink: Callable[[str], None] = print, *, with_headers: bool = False
) -> None:
    """Emit the report artifacts to some textual sink.

    Prints to stdout by default, but can also write to a logger by overriding the sink.

    Args:
        files: the output report artifacts from rendering simulation results.
        sink: a callable that accepts a string. Default is `print` to stdout.
        with_headers: a boolean controlling whether to emit artifact path names as headers.

    """
    for path, content in files.items():
        header = f"\n--- {path} ---\n" if with_headers else ""
        sink(header + content + "\n")


def render_static_content(
    static_files: Iterable[str],
    outdir: Path | None = None,
) -> ReportArtifacts:
    """Render static artifacts.

    These are files are just copied over as they don't need to be templated.
    Where an outdir is specified the rendered artifacts are saved to that
    directory eagerly as each file is rendered.

    Args:
        static_files: iterable of relative file paths as strings
        outdir: optional output directory

    Returns:
        Report artifacts that have been rendered.

    """
    artifacts = {}

    for name in static_files:
        artifacts[name] = render_static(path=name)
        if outdir is not None:
            artifact_path = outdir / name
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(artifacts[name])

    return artifacts
