# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim Scheduler Instrumentation."""

from dvsim.instrumentation.base import (
    CompositeInstrumentation,
    InstrumentationFragment,
    InstrumentationFragments,
    JobFragment,
    NoOpInstrumentation,
    SchedulerFragment,
    SchedulerInstrumentation,
    merge_instrumentation_report,
)
from dvsim.instrumentation.factory import InstrumentationFactory
from dvsim.instrumentation.metadata import MetadataInstrumentation, MetadataJobFragment
from dvsim.instrumentation.runtime import flush, get, set_instrumentation, set_report_path
from dvsim.instrumentation.timing import (
    TimingInstrumentation,
    TimingJobFragment,
    TimingSchedulerFragment,
)

__all__ = (
    "CompositeInstrumentation",
    "InstrumentationFactory",
    "InstrumentationFragment",
    "InstrumentationFragments",
    "JobFragment",
    "MetadataInstrumentation",
    "MetadataJobFragment",
    "NoOpInstrumentation",
    "SchedulerFragment",
    "SchedulerInstrumentation",
    "TimingInstrumentation",
    "TimingJobFragment",
    "TimingSchedulerFragment",
    "flush",
    "get",
    "merge_instrumentation_report",
    "set_instrumentation",
    "set_report_path",
)
