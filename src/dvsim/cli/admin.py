# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim CLI main entry point."""

import sys
from importlib.metadata import version
from pathlib import Path

import click

from dvsim.instrumentation.report.profile import RenderProfile


@click.group()
@click.version_option(version("dvsim"))
def cli() -> None:
    """DVSim Administration tool.

    Temporary tool for administration tasks for a DVSim project. The commands
    here are experimental and may change at any time. As functionality
    stabilises it will be moved over to the main `dvsim` command.
    """


@cli.group()
def dashboard() -> None:
    """Dashboard helper commands."""


@dashboard.command("gen")
@click.argument(
    "json_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "output_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--base-url",
    default=None,
    type=str,
)
def dashboard_gen(json_path: Path, output_dir: Path, base_url: str | None) -> None:
    """Generate a dashboard from a existing results JSON."""
    from dvsim.sim.dashboard import gen_badges, gen_dashboard  # noqa: PLC0415
    from dvsim.sim.data import SimResultsSummary  # noqa: PLC0415

    results: SimResultsSummary = SimResultsSummary.load(path=json_path)

    gen_dashboard(
        summary=results,
        path=output_dir,
        base_url=base_url,
    )

    gen_badges(
        summary=results,
        path=output_dir,
    )


@cli.group()
def report() -> None:
    """Reporting helper commands."""  # noqa: D401


@report.command("gen")
@click.argument(
    "json_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "output_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
def report_gen(json_path: Path, output_dir: Path) -> None:
    """Generate a report from a existing results JSON."""
    from dvsim.sim.data import SimResultsSummary  # noqa: PLC0415
    from dvsim.sim.report import gen_reports  # noqa: PLC0415

    summary: SimResultsSummary = SimResultsSummary.load(path=json_path)
    flow_results = summary.load_flow_results(
        base_path=json_path.parent,
    )

    gen_reports(
        summary=summary,
        flow_results=flow_results,
        path=output_dir,
    )


@report.command(
    "instrumentation", short_help="Generate an instrumentation report from existing metrics."
)
@click.argument(
    "json_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
@click.argument("output_dir", type=click.Path(file_okay=False, dir_okay=True, path_type=Path))
@click.option(
    "--profile",
    type=click.Choice([e.value for e in RenderProfile], case_sensitive=False),
    help="Set the rendering profile to control the detail vs. report optimization",
)
def instrumentation_report_gen(json_path: Path, output_dir: Path, profile: str | None) -> None:
    """Generate an instrumentation report from an existing metrics JSON."""
    from dvsim.instrumentation.records import InstrumentationResults  # noqa: PLC0415
    from dvsim.instrumentation.runtime import gen_html_report  # noqa: PLC0415

    render_profile = None if profile is None else RenderProfile(profile)
    results = InstrumentationResults.model_validate_json(json_path.read_text(encoding="utf-8"))
    gen_html_report(results, profile=render_profile, outdir=output_dir)


if __name__ == "__main__":
    sys.exit(cli())
