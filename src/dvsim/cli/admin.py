# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim CLI main entry point."""

from pathlib import Path

import click


@click.group()
def cli() -> None:
    """DVSim Administration tool.

    Temporary tool for administration tasks for a DVSim project. The commands
    here are experimental and may change at any time. As functionality
    stabilises it will be moved over to the main `dvsim` command.
    """


@cli.group()
def report() -> None:
    """Reporting helper commands."""


@report.command()
@click.argument(
    "json_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "output_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
def gen(json_path: Path, output_dir: Path) -> None:
    """Generate a report from a existing results JSON."""
    from dvsim.sim.data import SimResultsSummary
    from dvsim.sim.report import gen_reports

    results: SimResultsSummary = SimResultsSummary.load(path=json_path)

    gen_reports(summary=results, path=output_dir)
