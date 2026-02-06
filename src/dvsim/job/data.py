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

from pydantic import BaseModel, ConfigDict

from dvsim.job.status import JobStatus
from dvsim.launcher.base import ErrorMessage, Launcher
from dvsim.report.data import IPMeta, ToolMeta

__all__ = (
    "CompletedJobStatus",
    "JobSpec",
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


class JobSpec(BaseModel):
    """Job specification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the job"""

    job_type: str
    """Deployment type"""
    target: str
    """run phase [build, run, ...]"""

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
    timeout_mins: int | None
    """Timeout to apply to the launched job."""

    cmd: str
    """Command to run to execute the job."""
    exports: Mapping[str, str]
    """Environment variables to set in the context of the running job."""
    dry_run: bool
    """Go through the motions but don't actually run the job."""
    interactive: bool
    """Enable interactive mode."""
    gui: bool
    """Enable GUI mode."""

    odir: Path
    """Output directory for the job results files."""
    log_path: Path
    """Path for the job log file."""
    links: Mapping[JobStatus, Path]
    """Path for links directories."""

    # TODO: remove the need for these callables here
    pre_launch: Callable[[Launcher], None]
    """Callback function for pre-launch actions."""
    post_finish: Callable[[JobStatus], None]
    """Callback function for tidy up actions once the job is finished."""

    pass_patterns: Sequence[str]
    """regex patterns to match on to determine if the job is successful."""
    fail_patterns: Sequence[str]
    """regex patterns to match on to determine if the job has failed."""


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
    fail_msg: ErrorMessage
    """Error message."""
