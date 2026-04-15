# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job data models.

The JobSpec is used to capture all the information required to be able to
schedule a job. Once the job has finished a CompletedJobStatus is used to
capture the results of the job run.
"""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict

from dvsim.job.status import JobStatus
from dvsim.report.data import IPMeta, ToolMeta

__all__ = (
    "CompletedJobStatus",
    "JobSpec",
    "JobStatusInfo",
    "WorkspaceConfig",
)


class WorkspaceConfig(BaseModel):
    """Workspace configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: str
    """Time stamp of the run."""

    project_root: Path
    """Path to the project root."""
    scratch_root: Path
    """Path to the scratch directory root."""
    scratch_path: Path
    """Path within the scratch directory to use for this run."""


# A mapping of resource names to the max number of that resource available (or None if unbounded).
ResourceMapping: TypeAlias = dict[str, int | None]


class JobSpec(BaseModel):
    """Job specification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the job"""

    job_type: str
    """Deployment type"""
    target: str
    """run phase [build, run, ...]"""

    backend: str | None
    """The runtime backend to execute this job with. If not provided (None), this
    indicates that whatever is configured as the 'default' backend should be used.
    """

    resources: ResourceMapping | None
    """Resource requirements of the job. Maps the name of the resource to the amount
    of that resource that is required to run the job. If the scheduler is instructed
    to run with enforced resource limits, this limits per-resource parallelism.
    """

    seed: int | None
    """Seed if there is one."""

    full_name: str
    """Full name disambiguates across multiple cfg being run (example:
    'aes:default', 'uart:default' builds.
    """
    qual_name: str
    """Qualified name disambiguates the instance name with other instances
    of the same class (example: 'uart_smoke' reseeded multiple times
    needs to be disambiguated using the index -> '0.uart_smoke'.
    """

    block: IPMeta
    """IP block metadata."""
    tool: ToolMeta
    """Tool used in the simulation run."""
    workspace_cfg: WorkspaceConfig
    """Workspace configuration."""

    dependencies: list[str]
    """Full names of the other Jobs that this one depends on."""
    needs_all_dependencies_passing: bool
    """Wait for dependent jobs to pass before scheduling."""
    weight: int
    """Weight to apply to the scheduling priority."""
    timeout_mins: float | None
    """Timeout to apply to the launched job."""

    cmd: str
    """Command to run to execute the job."""
    exports: Mapping[str, str]
    """Environment variables to set in the context of the running job."""
    dry_run: bool
    """Go through the motions but don't actually run the job."""
    interactive: bool
    """Enable interactive mode."""

    odir: Path
    """Output directory for the job results files."""
    renew_odir: bool
    """A flag set to `true` to indicate that this job should "renew" its output directories,
    or to `false` if it should overwrite previous contents. Renewing a directory involves backing
    up the existing directory (up to some defined limit, at which point old backups are deleted)
    and then creating the new output directory. For example, one reason to set `renew_odir=True`
    might be to make use of an incremental/partition compile feature for a tool.
    """
    log_path: Path
    """Path for the job log file."""

    # TODO: remove the need for these callables here
    pre_launch: Callable[[], None]
    """Callback function for pre-launch actions."""
    post_finish: Callable[[JobStatus], None]
    """Callback function for tidy up actions once the job is finished."""

    pass_patterns: Sequence[str]
    """regex patterns to match on to determine if the job is successful."""
    fail_patterns: Sequence[str]
    """regex patterns to match on to determine if the job has failed."""

    @property
    def id(self) -> str:
        """Returns a string that uniquely identifies this job."""
        # The full name disambiguates jobs, so `id` is just an alias here.
        return self.full_name

    @property
    def timeout_secs(self) -> float | None:
        """Returns the timeout applied to the launched job, in seconds."""
        return None if self.timeout_mins is None else self.timeout_mins * 60


class JobStatusInfo(BaseModel):
    """Context about some sort of failure / error within a job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message: str
    """Human readable error message."""
    lines: Sequence[int | tuple[int, int]] | None = None
    """Relevant line information (in the job script or the job itself)."""
    context: Sequence[str] | None = None
    """Arbitrary context strings."""


class CompletedJobStatus(BaseModel):
    """Job status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the job"""
    job_type: str
    """Deployment type"""
    seed: int | None
    """Seed if there is one."""

    block: IPMeta
    """IP block metadata."""
    tool: ToolMeta
    """Tool used in the simulation run."""
    workspace_cfg: WorkspaceConfig
    """Workspace configuration."""

    full_name: str
    """Full name disambiguates across multiple cfg being run (example:
    'aes:default', 'uart:default' builds.
    """

    qual_name: str
    """Qualified name disambiguates the instance name with other instances
    of the same class (example: 'uart_smoke' reseeded multiple times
    needs to be disambiguated using the index -> '0.uart_smoke'.
    """

    target: str
    """run phase [build, run, ...]"""

    log_path: Path
    """Path for the job log file."""

    job_runtime: float
    """Duration of the job."""
    simulated_time: float
    """Simulation time."""

    status: JobStatus
    """Status of the job."""
    fail_msg: JobStatusInfo | None
    """Error message."""
