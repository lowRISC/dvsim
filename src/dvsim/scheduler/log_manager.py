# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim Scratch Job Log Manager."""

from collections.abc import Iterable
from pathlib import Path

from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus
from dvsim.utils import mk_symlink, rm_path


class LogManager:
    """Observes job state changes in the scheduler and manages scratch output directory links."""

    def __init__(self, jobs: Iterable[JobSpec]) -> None:
        """Construct a LogManager."""
        # Mapping from job ID -> last symlinked status
        self._links: dict[str, JobStatus] = {}

        # (Re)create the directories which will contain symlinks for each status
        workspace_cfgs = set()
        for job in jobs:
            if job.workspace_cfg in workspace_cfgs:
                continue

            workspace_cfgs.add(job.workspace_cfg)
            for status in JobStatus:
                if self.has_symlink_dir(status):
                    link_dir = self.status_symlink_dir(job, status)
                    rm_path(link_dir)
                    link_dir.mkdir(parents=True)

    @staticmethod
    def has_symlink_dir(status: JobStatus) -> bool:
        """Check whether a job status should have an output directory for symlinks or not."""
        return status.is_terminal or status == JobStatus.RUNNING

    def status_symlink_dir(self, job: JobSpec, status: JobStatus) -> Path:
        """Get the output dir for symlinking jobs of a given status."""
        return job.workspace_cfg.scratch_path / status.name.lower()

    def status_symlink(self, job: JobSpec, status: JobStatus) -> Path:
        """Get the output path for a symlink of a job for a given status."""
        return self.status_symlink_dir(job, status) / job.qual_name

    def _link_job_output_directory(self, job: JobSpec, status: JobStatus) -> None:
        """Symbolic (soft) link the job's output directory based on its status.

        The status directories (e.g. `passed/`, `failed/`) in the scratch area then provide a
        quick mechanism for traversing the list of jobs that were executed.
        """
        old_status = self._links.get(job.id, None)
        if old_status == status:
            return

        link_dest = self.status_symlink(job, status)
        self._links[job.id] = status

        # If the symlink already exists (e.g. created by legacy launcher), just keep it.
        # TODO: when all launchers are migrated this check can be removed.
        if link_dest.exists() and link_dest.is_symlink():
            return
        mk_symlink(path=job.odir, link=link_dest)

        # Delete the previous symlink if it exists
        if old_status is not None:
            old_link_dest = self.status_symlink(job, old_status)
            rm_path(old_link_dest)

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify the LogManager when a job status has changed."""
        # Only create linked output directories for defined links (terminal state or running).
        if self.has_symlink_dir(status):
            self._link_job_output_directory(job, status)
