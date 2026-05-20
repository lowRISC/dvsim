# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""An enum definition for the various job statuses."""

from enum import Enum

__all__ = ("JobStatus",)


class JobStatus(Enum):
    """Status of a Job."""

    SCHEDULED = "Scheduled"  # Waiting for dependencies
    QUEUED = "Queued"  # Dependencies satisfied, waiting to be dispatched
    RUNNING = "Running"  # Dispatched to a backend and actively executing
    PASSED = "Passed"  # Completed successfully
    FAILED = "Failed"  # Completed with failure
    KILLED = "Killed"  # Forcibly terminated or never executed

    @property
    def shorthand(self) -> str:
        """Shorthand for the job status, e.g. 'R' for 'RUNNING'."""
        return self.name[0]

    @property
    def is_terminal(self) -> bool:
        """Whether this status corresponds to some ended job."""
        return self in (JobStatus.PASSED, JobStatus.FAILED, JobStatus.KILLED)
