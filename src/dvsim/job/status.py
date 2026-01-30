# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""An enum definition for the various job statuses."""

from enum import Enum

__all__ = ("JobStatus",)


class JobStatus(Enum):
    """Status of a Job."""

    QUEUED = 0
    DISPATCHED = 1
    PASSED = 2
    FAILED = 3
    KILLED = 4

    @property
    def shorthand(self) -> str:
        """Shorthand for the job status, e.g. 'D' for 'Dispatched'."""
        return self.name[0]

    @property
    def ended(self) -> bool:
        """Whether this status corresponds to some ended job."""
        return self in (JobStatus.PASSED, JobStatus.FAILED, JobStatus.KILLED)
