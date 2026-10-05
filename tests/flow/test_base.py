# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the flow base class.

Only the scheduler observer hook for now, which is the one thing on `FlowCfg` a flow opts into
rather than inherits.
"""

from types import SimpleNamespace

from hamcrest import assert_that, is_, none

from dvsim.flow.base import FlowCfg


def test_the_base_flow_observes_nothing() -> None:
    """A flow with no use for job outcomes hands over no observer, so the scheduler notifies none.

    Called unbound against a stand-in, since building a real flow config needs a whole hjson cfg
    and none of it bears on the answer.
    """
    assert_that(FlowCfg.job_completion_callback(SimpleNamespace()), is_(none()))
