# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate reports."""

from pathlib import Path

from dvsim.logging import log
from dvsim.report.data import FlowResults, ResultsSummary
from dvsim.templates.render import render_template

__all__ = (
    "gen_block_report",
    "gen_summary_report",
)


def gen_block_report(results: FlowResults, path: Path) -> None:
    """Generate a block report.

    Args:
        results: flow results for the block
        path: output directory path

    """
    log.debug("generating report '%s'", results.block.name)

    path.mkdir(parents=True, exist_ok=True)

    # Save the JSON version
    (path / f"{results.block.name}.json").write_text(results.model_dump_json())

    # Generate HTML report
    (path / f"{results.block.name}.html").write_text(
        render_template(
            path="reports/block_report.html",
            data={"results": results},
        ),
    )


def gen_summary_report(summary: ResultsSummary, path: Path) -> None:
    """Generate a summary report.

    Args:
        summary: overview of the block results
        path: output directory path

    """
    log.debug("generating summary report")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Save the JSON version
    (path / "index.json").write_text(summary.model_dump_json())

    # Generate HTML report
    (path / "index.html").write_text(
        render_template(
            path="reports/summary_report.html",
            data={
                "summary": summary,
            },
        ),
    )
