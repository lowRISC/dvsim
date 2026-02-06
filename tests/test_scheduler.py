# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim scheduler."""

import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from dvsim.job.data import JobSpec, WorkspaceConfig
from dvsim.job.status import JobStatus
from dvsim.launcher.base import ErrorMessage, Launcher, LauncherBusyError, LauncherError

__all__ = ()


@dataclass
class MockJob:
    """Mock of a single DVSim job to allow testing of scheduler behaviour.

    Attributes:
        status_thresholds: Ordered list of (count, status) where the job should report <status>
            after being polled <count> or more times.
        default_status: Default status to report when polled, if not using `status_thresholds`.
        launch_count: Number of times launched so far.
        poll_count: Number of times polled so far.
        kill_count: Number of times killed so far.
        kill_time: Time that `kill()` should sleep/block for when called.
        launcher_error: Any error to raise on `launch()`.
        launcher_busy_error: Tuple (count, error) where <error> should be raised for the first
            <count> launch attempts.

    """

    status_thresholds: list[tuple[int, JobStatus]] | None = None
    default_status: JobStatus = JobStatus.PASSED
    launch_count: int = 0
    poll_count: int = 0
    kill_count: int = 0
    kill_time: float | None = None
    launcher_error: LauncherError | None = None
    launcher_busy_error: tuple[int, LauncherBusyError] | None = None

    @property
    def current_status(self) -> JobStatus:
        """The current status of the job, based on its status configuration & poll count."""
        if not self.status_thresholds:
            return self.default_status
        current_status = self.default_status
        for target_count, status in self.status_thresholds:
            if target_count <= self.poll_count:
                current_status = status
            else:
                break
        return current_status


class MockLauncherContext:
    """Context for a mocked launcher to allow testing of scheduler behaviour."""

    def __init__(self) -> None:
        self._configs = {}
        self._running = set()
        self.max_concurrent = 0
        self.order_started = []
        self.order_completed = []

    def update_running(self, job: JobSpec) -> None:
        """Update the mock context to record that a given job is running."""
        job_name = (job.full_name, job.qual_name)
        if job_name not in self._running:
            self._running.add(job_name)
            self.max_concurrent = max(self.max_concurrent, len(self._running))
            self.order_started.append(job)

    def update_completed(self, job: JobSpec) -> None:
        """Update the mock context to record that a given job has completed (stopped running)."""
        job_name = (job.full_name, job.qual_name)
        if job_name in self._running:
            self._running.remove(job_name)
            self.order_completed.append(job)

    def set_config(self, job: JobSpec, config: MockJob) -> None:
        """Configure the behaviour for mocking a specified job."""
        self._configs[(job.full_name, job.qual_name)] = config

    def get_config(self, job: JobSpec) -> MockJob | None:
        """Retrieve the mock configuration/state of a specified job."""
        return self._configs.get((job.full_name, job.qual_name))


class MockLauncher(Launcher):
    """Mock of a launcher, used for testing scheduler behaviour."""

    # Default to polling instantly so we don't wait additional time in tests
    poll_freq = 0

    # The launcher is currently provided to the scheduler as a type that inherits from the
    # Launcher class. As a result of this design, we must store the mock context as a class
    # attribute, which we directly update at the start of each test.
    #
    # TODO: In the future, the scheduler interface should be changed to a `Callable`, so
    # that we can more easily do dependency-injection by providing the context via the
    # constructor using partial arguments.
    mock_context: MockLauncherContext | None = None

    @staticmethod
    def prepare_workspace(cfg: WorkspaceConfig) -> None: ...

    @staticmethod
    def prepare_workspace_for_cfg(cfg: WorkspaceConfig) -> None: ...

    def _do_launch(self) -> None:
        """Launch the job."""
        if self.mock_context is None:
            return
        mock = self.mock_context.get_config(self.job_spec)
        if mock is not None:
            # Emulate any configured launcher errors for the job at this stage
            mock.launch_count += 1
            if mock.launcher_busy_error and mock.launch_count <= mock.launcher_busy_error[0]:
                raise mock.launcher_busy_error[1]
            if mock.launcher_error:
                raise mock.launcher_error
            status = mock.current_status
            if status == JobStatus.QUEUED:
                return  # Do not mark as running if still mocking a queued status.
        self.mock_context.update_running(self.job_spec)

    def poll(self) -> JobStatus:
        """Poll the launched job for completion."""
        # If there is no mock context / job config, just complete & report "PASSED".
        if self.mock_context is None:
            return JobStatus.PASSED
        mock = self.mock_context.get_config(self.job_spec)
        if mock is None:
            self.mock_context.update_completed(self.job_spec)
            return JobStatus.PASSED

        # Increment the poll count, and update the run state based on the reported status
        mock.poll_count += 1
        status = mock.current_status
        if status.ended:
            self.mock_context.update_completed(self.job_spec)
        elif status == JobStatus.DISPATCHED:
            self.mock_context.update_running(self.job_spec)
        return status

    def kill(self) -> None:
        """Kill the running process."""
        if self.mock_context is not None:
            # Update the kill count and perform any configured kill delay.
            mock = self.mock_context.get_config(self.job_spec)
            if mock is not None:
                mock.kill_count += 1
                if mock.kill_time is not None:
                    time.sleep(mock.kill_time)
            self.mock_context.update_completed(self.job_spec)
        self._post_finish(
            JobStatus.KILLED,
            ErrorMessage(line_number=None, message="Job killed!", context=[]),
        )


@pytest.fixture
def mock_ctx() -> MockLauncherContext:
    """Fixture for generating a unique mock launcher context per test."""
    return MockLauncherContext()


@pytest.fixture
def mock_launcher(mock_ctx: MockLauncherContext) -> type[MockLauncher]:
    """Fixture for generating a unique mock launcher class/type per test."""

    class TestMockLauncher(MockLauncher):
        pass

    TestMockLauncher.mock_context = mock_ctx
    return TestMockLauncher


@dataclass
class Fxt:
    """Collection of fixtures used for mocking and testing the scheduler."""

    tmp_path: Path
    mock_ctx: MockLauncherContext
    mock_launcher: type[MockLauncher]


@pytest.fixture
def fxt(tmp_path: Path, mock_ctx: MockLauncherContext, mock_launcher: type[MockLauncher]) -> Fxt:
    """Fixtures used for mocking and testing the scheduler."""
    return Fxt(tmp_path, mock_ctx, mock_launcher)
