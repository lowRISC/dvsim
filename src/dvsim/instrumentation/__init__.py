# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim Scheduler Instrumentation."""

from dvsim.instrumentation.base import InstrumentationAggregator, SchedulerInstrumentation
from dvsim.instrumentation.factory import InstrumentationFactory
from dvsim.instrumentation.records import (
    InstrumentationMetrics,
    InstrumentationResults,
    JobMetrics,
    SchedulerMetrics,
)
from dvsim.instrumentation.runtime import (
    flush,
    gen_html_report,
    get,
    get_report,
    set_instrumentation,
    set_report_path,
)

__all__ = (
    "InstrumentationAggregator",
    "InstrumentationFactory",
    "InstrumentationMetrics",
    "InstrumentationResults",
    "JobMetrics",
    "SchedulerInstrumentation",
    "SchedulerMetrics",
    "flush",
    "gen_html_report",
    "get",
    "get_report",
    "set_instrumentation",
    "set_report_path",
)
