# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim scheduler."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from hamcrest import assert_that, empty, equal_to, only_contains

from dvsim.job.data import CompletedJobStatus, JobSpec, WorkspaceConfig
from dvsim.job.status import JobStatus
from dvsim.launcher.base import ErrorMessage, Launcher, LauncherBusyError, LauncherError
from dvsim.report.data import IPMeta, ToolMeta
from dvsim.scheduler import Scheduler

__all__ = ()


# Default scheduler test timeout to handle infinite loops in the scheduler
DEFAULT_TIMEOUT = 0.5


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


def ip_meta_factory(**overrides: str | None) -> IPMeta:
    """Create an IPMeta from a set of default values, for use in testing."""
    meta = {
        "name": "test_ip",
        "variant": None,
        "commit": "test_commit",
        "branch": "test_branch",
        "url": "test_url",
    }
    meta.update(overrides)
    return IPMeta(**meta)


def tool_meta_factory(name: str = "test_tool", version: str = "test_version") -> ToolMeta:
    """Create a ToolMeta from a set of default values, for use in testing."""
    return ToolMeta(name=name, version=version)


def build_workspace(
    tmp_path: Path, run_name: str = "test", **overrides: str | Path | None
) -> WorkspaceConfig:
    """Create a WorkspaceConfig with a set of defaults and given temp paths for testing."""
    config = {
        "timestamp": "test_timestamp",
        "project_root": tmp_path / "root",
        "scratch_root": tmp_path / "scratch",
        "scratch_path": tmp_path / "scratch" / run_name,
    }
    config.update(overrides)
    return WorkspaceConfig(**config)


@dataclass(frozen=True)
class JobSpecPaths:
    """A bundle of paths for testing a Job / JobSpec."""

    output: Path
    log: Path
    statuses: dict[JobStatus, Path]


def make_job_paths(
    tmp_path: Path, job_name: str = "test", *, ensure_exists: bool = False
) -> JobSpecPaths:
    """Generate a set of paths to use for testing a job (JobSpec)."""
    root = tmp_path / job_name
    output = root / "out"
    log = root / "log.txt"
    statuses = {}
    for status in JobStatus:
        if status == JobStatus.QUEUED:
            continue
        status_dir = output / status.name.lower()
        statuses[status] = status_dir
        if ensure_exists:
            Path(status_dir).mkdir(exist_ok=True, parents=True)
    return JobSpecPaths(output=output, log=log, statuses=statuses)


def job_spec_factory(
    tmp_path: Path,
    paths: JobSpecPaths | None = None,
    **overrides: object,
) -> JobSpec:
    """Create a JobSpec from a set of default values, for use in testing."""
    spec = {
        "name": "test_job",
        "job_type": "mock_type",
        "target": "mock_target",
        "seed": None,
        "dependencies": [],
        "needs_all_dependencies_passing": True,
        "weight": 1,
        "timeout_mins": None,
        "cmd": "echo 'test_cmd'",
        "exports": {},
        "dry_run": False,
        "interactive": False,
        "gui": False,
        "pre_launch": lambda _: None,
        "post_finish": lambda _: None,
        "pass_patterns": [],
        "fail_patterns": [],
    }
    spec.update(overrides)

    # Add job file paths if they do not exist
    if paths is None:
        paths = make_job_paths(tmp_path, job_name=spec["name"])
    if "odir" not in spec:
        spec["odir"] = paths.output
    if "log_path" not in spec:
        spec["log_path"] = paths.log
    if "links" not in spec:
        spec["links"] = paths.statuses

    # Define the IP metadata, tool metadata and workspace if they do not exist
    if "block" not in spec:
        spec["block"] = ip_meta_factory()
    if "tool" not in spec:
        spec["tool"] = tool_meta_factory()
    if "workspace_cfg" not in spec:
        spec["workspace_cfg"] = build_workspace(tmp_path)

    # Use the name as the full name & qual name if not manually specified
    if "full_name" not in spec:
        spec["full_name"] = spec["name"]
    if "qual_name" not in spec:
        spec["qual_name"] = spec["name"]
    return JobSpec(**spec)


def make_many_jobs(
    tmp_path: Path,
    n: int,
    *,
    workspace: WorkspaceConfig | None = None,
    per_job: Callable[[int], dict[str, Any]] | None = None,
    interdeps: dict[int, list[int]] | None = None,
    ensure_paths_exist: bool = False,
    vary_targets: bool = False,
    reverse: bool = False,
    **overrides: object,
) -> list[JobSpec]:
    """Create many JobSpecs at once for scheduler test purposes.

    Arguments:
        tmp_path: The path to the temp dir to use for creating files.
        n: The number of jobs to create.
        workspace: The workspace configuration to use by default for jobs.
        per_job: Given the index of a job, this func returns specific per-job overrides.
        interdeps: A directed edge-list of job dependencies (via their indexes).
        ensure_paths_exist: Whether to create generated job output paths.
        vary_targets: Whether to automatically generate unique targets per job.
        reverse: Optionally reverse the output jobs.
        overrides: Any additional kwargs to apply to *every* created job.

    """
    # Create the workspace to share between jobs if not given one.
    if workspace is None:
        workspace = build_workspace(tmp_path)

    # Create the job parameters
    job_specs = []
    for i in range(n):
        name = f"job_{i}"
        job = {
            "name": name,
            "paths": make_job_paths(tmp_path, job_name=name, ensure_exists=ensure_paths_exist),
            "target": f"target_{i}" if vary_targets else "mock_target",
            "workspace_cfg": workspace,
        }
        # Apply global overrides
        job.update(overrides)
        # Fetch and apply per-job overrides
        if per_job:
            job.update(per_job(i))
        job_specs.append(job)

    # Create dependencies between the jobs
    jobs = []
    for i, job in enumerate(job_specs):
        if interdeps:
            deps = job.setdefault("dependencies", [])
            deps.extend(job_specs[d]["name"] for d in interdeps.get(i, []))
        jobs.append(job_spec_factory(tmp_path, **job))

    return jobs[::-1] if reverse else jobs


def _assert_result_status(
    result: Sequence[CompletedJobStatus], num: int, expected: JobStatus = JobStatus.PASSED
) -> None:
    """Assert a common result pattern, checking the number & status of scheduler results."""
    assert_that(len(result), equal_to(num))
    statuses = [c.status for c in result]
    assert_that(statuses, only_contains(expected))


class TestScheduling:
    """Unit tests for the scheduling decisions of the scheduler."""

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_empty(fxt: Fxt) -> None:
        """Test that the scheduler can handle being given no jobs."""
        result = Scheduler([], fxt.mock_launcher).run()
        assert_that(result, empty())

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_job_run(fxt: Fxt) -> None:
        """Small smoketest that the scheduler can actually run a valid job."""
        job = job_spec_factory(fxt.tmp_path)
        result = Scheduler([job], fxt.mock_launcher).run()
        _assert_result_status(result, 1)

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_many_jobs_run(fxt: Fxt) -> None:
        """Smoketest that the scheduler can run multiple valid jobs."""
        job_specs = make_many_jobs(fxt.tmp_path, n=5)
        result = Scheduler(job_specs, fxt.mock_launcher).run()
        _assert_result_status(result, 5)

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_duplicate_jobs(fxt: Fxt) -> None:
        """Test that the scheduler does not double-schedule jobs with duplicate names."""
        workspace = build_workspace(fxt.tmp_path)
        job_specs = make_many_jobs(fxt.tmp_path, n=3, workspace=workspace)
        job_specs += make_many_jobs(fxt.tmp_path, n=6, workspace=workspace)
        for _ in range(10):
            job_specs.append(job_spec_factory(fxt.tmp_path, name="extra_job"))
            job_specs.append(job_spec_factory(fxt.tmp_path, name="extra_job_2"))
        result = Scheduler(job_specs, fxt.mock_launcher).run()
        # Current behaviour expects duplicate jobs to be *silently ignored*.
        # We should therefore have 3 + 3 + 2 = 8 jobs.
        _assert_result_status(result, 8)
        names = [c.name for c in result]
        # Check names of all jobs are unique (i.e. no duplicates are returned).
        assert_that(len(names), equal_to(len(set(names))))

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize("num_jobs", [2, 3, 5, 10, 20, 100])
    def test_parallel_dispatch(fxt: Fxt, num_jobs: int) -> None:
        """Test that many jobs can be dispatched in parallel."""
        jobs = make_many_jobs(fxt.tmp_path, num_jobs)
        scheduler = Scheduler(jobs, fxt.mock_launcher)
        assert_that(fxt.mock_ctx.max_concurrent, equal_to(0))
        result = scheduler.run()
        _assert_result_status(result, num_jobs)
        assert_that(fxt.mock_ctx.max_concurrent, equal_to(num_jobs))

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize("num_jobs", [5, 10, 20])
    @pytest.mark.parametrize("max_parallel", [1, 5, 15, 25])
    def test_max_parallel(fxt: Fxt, num_jobs: int, max_parallel: int) -> None:
        """Test that max parallel limits of launchers are used & respected."""
        jobs = make_many_jobs(fxt.tmp_path, num_jobs)
        fxt.mock_launcher.max_parallel = max_parallel
        scheduler = Scheduler(jobs, fxt.mock_launcher)
        assert_that(fxt.mock_ctx.max_concurrent, equal_to(0))
        result = scheduler.run()
        _assert_result_status(result, num_jobs)
        assert_that(fxt.mock_ctx.max_concurrent, equal_to(min(num_jobs, max_parallel)))

    @staticmethod
    @pytest.mark.parametrize("polls", [5, 10, 50])
    @pytest.mark.parametrize("final_status", [JobStatus.PASSED, JobStatus.FAILED, JobStatus.KILLED])
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_repeated_poll(fxt: Fxt, polls: int, final_status: JobStatus) -> None:
        """Test that the scheduler will repeatedly poll for a dispatched job."""
        job = job_spec_factory(fxt.tmp_path)
        fxt.mock_ctx.set_config(
            job, MockJob(status_thresholds=[(0, JobStatus.DISPATCHED), (polls, final_status)])
        )
        result = Scheduler([job], fxt.mock_launcher).run()
        _assert_result_status(result, 1, expected=final_status)
        config = fxt.mock_ctx.get_config(job)
        if config is not None:
            assert_that(config.poll_count, equal_to(polls))

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_no_over_poll(fxt: Fxt) -> None:
        """Test that the schedule stops polling when it sees `PASSED`, and does not over-poll."""
        jobs = make_many_jobs(fxt.tmp_path, 10)
        polls = [(i + 1) * 10 for i in range(10)]
        for i in range(10):
            fxt.mock_ctx.set_config(
                jobs[i],
                MockJob(
                    status_thresholds=[(0, JobStatus.DISPATCHED), (polls[i], JobStatus.PASSED)]
                ),
            )
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 10)
        # Check we do not unnecessarily over-poll the jobs
        for i in range(10):
            config = fxt.mock_ctx.get_config(jobs[i])
            if config is not None:
                assert_that(config.poll_count, equal_to(polls[i]))

    @staticmethod
    @pytest.mark.xfail(
        reason="DVSim currently errors on this case. When DVSim dispatches and thus launches a"
        " job, it is only set to running after the launch. If a launcher error occurs, it"
        " immediately invokes `_kill_item` which tries to remove it from the list of running jobs"
        " (where it does not exist)."
    )
    def test_launcher_error(fxt: Fxt) -> None:
        """Test that the launcher correctly handles an error during job launching."""
        job = job_spec_factory(fxt.tmp_path, paths=make_job_paths(fxt.tmp_path, ensure_exists=True))
        fxt.mock_ctx.set_config(
            job,
            MockJob(
                status_thresholds=[(0, JobStatus.DISPATCHED), (10, JobStatus.PASSED)],
                launcher_error=LauncherError("abc"),
            ),
        )
        result = Scheduler([job], fxt.mock_launcher).run()
        # On a launcher error, the job has failed and should be killed.
        _assert_result_status(result, 1, expected=JobStatus.KILLED)

    @staticmethod
    @pytest.mark.parametrize("busy_polls", [1, 2, 5, 10])
    def test_launcher_busy_error(fxt: Fxt, busy_polls: int) -> None:
        """Test that the launcher correctly handles the launcher busy case."""
        job = job_spec_factory(fxt.tmp_path)
        err_mock = (busy_polls, LauncherBusyError("abc"))
        fxt.mock_ctx.set_config(
            job,
            MockJob(
                status_thresholds=[(0, JobStatus.DISPATCHED), (10, JobStatus.PASSED)],
                launcher_busy_error=err_mock,
            ),
        )
        result = Scheduler([job], fxt.mock_launcher).run()
        # We expect to have successfully launched and ran, eventually.
        _assert_result_status(result, 1)
        # Check that the scheduler tried to `launch()` the correct number of times.
        config = fxt.mock_ctx.get_config(job)
        if config is not None:
            assert_that(config.launch_count, equal_to(busy_polls + 1))
