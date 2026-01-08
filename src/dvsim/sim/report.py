# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate reports."""

from pathlib import Path

from dvsim.logging import log
from dvsim.sim.data import SimFlowResults, SimResultsSummary
from dvsim.templates.render import render_static, render_template

__all__ = (
    "gen_block_report",
    "gen_reports",
    "gen_summary_report",
)


def gen_block_report(results: SimFlowResults, path: Path) -> None:
    """Generate a block report.

    Args:
        results: flow results for the block
        path: output directory path

    """
    file_name = (
        f"{results.block.name}_{results.block.variant}"
        if results.block.variant
        else results.block.name
    )

    log.debug("generating report '%s'", file_name)

    path.mkdir(parents=True, exist_ok=True)

    # Save the JSON version
    (path / f"{file_name}.json").write_text(results.model_dump_json())

    # Generate HTML report
    (path / f"{file_name}.html").write_text(
        render_template(
            path="reports/block_report.html",
            data={"results": results},
        ),
    )


def gen_summary_report(summary: SimResultsSummary, path: Path) -> None:
    """Generate a summary report.

    Args:
        summary: overview of the block results
        path: output directory path

    """
    log.debug("generating summary report")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Save the JSON version
    (path / "index.json").write_text(summary.model_dump_json())

    # Generate style CSS
    for name in (
        "css/style.css",
        "css/bootstrap.min.css",
        "js/bootstrap.bundle.min.js",
        "js/htmx.min.js",
    ):
        output = path / name

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_static(path=name))

    # HTMX wrapper
    (path / "index.html").write_text(render_template(path="reports/wrapper.html"))

    # Generate HTML report
    (path / "summary.html").write_text(
        render_template(
            path="reports/summary_report.html",
            data={
                "summary": summary,
            },
        ),
    )


def gen_reports(summary: SimResultsSummary, path: Path) -> None:
    """Generate a full set of reports for the given regression run.

    Args:
        summary: overview of the block results
        path: output directory path

    """
    gen_summary_report(summary=summary, path=path)

    for flow_result in summary.flow_results.values():
        gen_block_report(results=flow_result, path=path)
