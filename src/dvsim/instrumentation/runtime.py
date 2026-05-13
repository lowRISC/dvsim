# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation runtime implementation."""

from pathlib import Path

from dvsim.instrumentation.base import InstrumentationAggregator, InstrumentationResults
from dvsim.instrumentation.report import (
    RenderProfile,
    ReportVisualizationRegistry,
    render_html_report,
)
from dvsim.logging import log

__all__ = (
    "flush",
    "gen_html_report",
    "get",
    "get_report",
    "set_instrumentation",
    "set_report_path",
)


class _Runtime:
    """Runtime singleton for the configured scheduler instrumentation."""

    def __init__(self) -> None:
        """Construct a Runtime for the scheduler instrumentation."""
        self.instrumentation: InstrumentationAggregator | None = None
        self.report_path: Path | None = None
        self.report: InstrumentationResults | None = None


_runtime = _Runtime()


def set_instrumentation(instrumentation: InstrumentationAggregator | None) -> None:
    """Configure the global instrumentation singleton."""
    _runtime.instrumentation = instrumentation


def set_report_path(path: Path | None) -> None:
    """Configure the instrumentation report path."""
    _runtime.report_path = path


def get() -> InstrumentationAggregator | None:
    """Get the configured global instrumentation."""
    return _runtime.instrumentation


def flush() -> InstrumentationResults | None:
    """Dump the instrumentation report as JSON to the configured report path."""
    if _runtime.instrumentation is None:
        return None

    _runtime.report = _runtime.instrumentation.collect()

    if _runtime.report_path:
        log.info("Dumping JSON instrumentation report...")
        if _runtime.report_path.is_dir():
            raise ValueError("Metric report path cannot be a directory.")
        try:
            _runtime.report_path.parent.mkdir(parents=True, exist_ok=True)
            _runtime.report_path.write_text(
                _runtime.report.model_dump_json(indent=2, exclude_none=True)
            )
            log.info("JSON instrumentation report dumped to: %s", str(_runtime.report_path))
        except (OSError, FileNotFoundError) as e:
            log.error(
                "Error writing instrumented metrics to %s: %s", str(_runtime.report_path), str(e)
            )

    return _runtime.report


def get_report() -> InstrumentationResults | None:
    """Get the latest flushed instrumentation report contents, if any exist."""
    return _runtime.report


def gen_html_report(
    results: InstrumentationResults,
    *,
    profile: RenderProfile | None = None,
    outdir: Path | None = None,
    json_path: Path | None = None,
) -> None:
    """Generate a HTML report of the instrumentation results with rendered visualizations.

    Args:
        results: The instrumentation results to render a HTML report for.
        profile: Optional rendering profile to customize level of detail vs. report optimization.
        outdir: The path to the directory to write the generated HTML report files to. If not
          provided, this defaults to the parent directory of the configured report path.
        json_path: The path to the metrics.json file. If not provided, this defaults to the
          configured report path (if it exists).

    """
    if outdir is None:
        if _runtime.report_path is None:
            return
        outdir = _runtime.report_path.parent

    if json_path is None:
        json_path = _runtime.report_path

    log.debug("HTML instrumentation report will be written to %s", outdir)
    visualizations = ReportVisualizationRegistry.create(profile)
    render_html_report(results, visualizations=visualizations, outdir=outdir, json_path=json_path)
