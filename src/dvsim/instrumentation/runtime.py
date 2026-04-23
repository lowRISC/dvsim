# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation for timing-related information."""

import json
from pathlib import Path
from typing import Any

from dvsim.instrumentation.base import InstrumentationAggregator
from dvsim.logging import log

__all__ = (
    "flush",
    "get",
    "get_report",
    "set_instrumentation",
    "set_report_path",
)


class _Runtime:
    def __init__(self) -> None:
        self.instrumentation: InstrumentationAggregator | None = None
        self.report_path: Path | None = None
        self.report: dict[str, Any] | None = None


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


def flush() -> dict[str, Any] | None:
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
            _runtime.report_path.write_text(json.dumps(_runtime.report, indent=2))
            log.info("JSON instrumentation report dumped to: %s", str(_runtime.report_path))
        except (OSError, FileNotFoundError) as e:
            log.error(
                "Error writing instrumented metrics to %s: %s", str(_runtime.report_path), str(e)
            )

    return _runtime.report


def get_report() -> dict[str, Any] | None:
    """Get the latest flushed instrumentation report contents, if any exist."""
    return _runtime.report
