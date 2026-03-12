# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate dashboard.

The dashboard is a cut down version of the full report where a simpler summary
is required than the full report simulation summary. This is intended to be used
on a separate website and links back to the detailed report if required.

This is intended to generate a dashboard that could be used on the OpenTitan
and automatically i.e. https://opentitan.org/dashboard/index.html
"""

from pathlib import Path

from dvsim.logging import log
from dvsim.report.artifacts import render_static_content
from dvsim.sim.data import SimResultsSummary
from dvsim.templates.render import render_template

__all__ = ("gen_dashboard",)


def gen_dashboard(
    summary: SimResultsSummary,
    path: Path,
    base_url: str | None = None,
) -> None:
    """Generate a summary dashboard.

    Args:
        summary: overview of the block results
        path: output directory path
        base_url: override the base URL for links

    """
    log.debug("generating results dashboard")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Generate the JS and CSS files
    render_static_content(
        static_files=[
            "css/style.css",
            "css/bootstrap.min.css",
            "js/bootstrap.bundle.min.js",
            "js/htmx.min.js",
        ],
        outdir=path,
    )

    (path / "dashboard.html").write_text(
        render_template(
            path="dashboard/dashboard.html",
            data={
                "summary": summary,
                "base_url": base_url,
            },
        )
    )
