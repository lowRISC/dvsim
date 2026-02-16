# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation for timing-related information."""

from pathlib import Path

from dvsim.instrumentation.base import SchedulerInstrumentation

__all__ = (
    "flush",
    "get",
    "set_instrumentation",
    "set_report_path",
)


class _Runtime:
    def __init__(self) -> None:
        self.instrumentation: SchedulerInstrumentation | None = None
        self.report_path: Path | None = None


_runtime = _Runtime()


def set_instrumentation(instrumentation: SchedulerInstrumentation | None) -> None:
    """Configure the global instrumentation singleton."""
    _runtime.instrumentation = instrumentation


def set_report_path(path: Path | None) -> None:
    """Configure the instrumentation report path."""
    _runtime.report_path = path


def get() -> SchedulerInstrumentation | None:
    """Get the configured global instrumentation."""
    return _runtime.instrumentation


def flush() -> None:
    """Dump the instrumentation report as JSON to the configured report path."""
    if _runtime.instrumentation is None or not _runtime.report_path:
        return
    _runtime.instrumentation.dump_json_report(_runtime.report_path)
