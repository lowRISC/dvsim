# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim Scratch Job Log Manager."""

from pathlib import Path

from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus
from dvsim.utils import mk_symlink, rm_path


class LogManager:
    """Observes job state changes in the scheduler and manages scratch output directory links."""

    def __init__(self) -> None:
        """Construct a LogManager."""
        # Mapping from job ID -> last symlinked status
        self._links: dict[str, JobStatus] = {}

    def _link_job_output_directory(self, job: JobSpec, status: JobStatus) -> None:
        """Symbolic (soft) link the job's output directory based on its status.

        The status directories (e.g. `passed/`, `failed/`) in the scratch area then provide a
        quick mechanism for traversing the list of jobs that were executed.
        """
        old_status = self._links.get(job.id, None)
        if old_status == status:
            return

        link_dest = Path(job.links[status], job.qual_name)
        self._links[job.id] = status

        # If the symlink already exists (e.g. created by legacy launcher), just keep it.
        # TODO: when all launchers are migrated this check can be removed.
        if link_dest.exists() and link_dest.is_symlink():
            return
        mk_symlink(path=job.odir, link=link_dest)

        # Delete the previous symlink if it exists
        if old_status is not None:
            old_link_dest = Path(job.links[old_status], job.qual_name)
            rm_path(old_link_dest)

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify the LogManager when a job status has changed."""
        # Only create linked output directories for defined links (terminal state or running).
        if status in job.links:
            self._link_job_output_directory(job, status)
