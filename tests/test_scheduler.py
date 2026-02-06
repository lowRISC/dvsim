# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim scheduler."""

import multiprocessing
import os
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from types import FrameType
from typing import Any

import pytest
from hamcrest import any_of, assert_that, empty, equal_to, has_item, only_contains

from dvsim.job.data import CompletedJobStatus, JobSpec, WorkspaceConfig
from dvsim.job.status import JobStatus
from dvsim.launcher.base import ErrorMessage, Launcher, LauncherBusyError, LauncherError
from dvsim.report.data import IPMeta, ToolMeta
from dvsim.scheduler import Scheduler

__all__ = ()

# Common reasoning for expected failures to avoid duplication across tests.
# Ideally these will be removed as incorrect behaviour is fixed.
FAIL_DEP_ON_MULTIPLE_TARGETS = """
DVSim cannot handle dependency fan-in (i.e. depending on jobs) across multiple targets.

Specifically, when all successors of the first target are initially enqueued, they are
removed from the `scheduled` queues. If any item in another target then also depends
on those items (i.e. across *another* target), then the completion of these items will
in turn attempt to enqueue their own successors, which cannot be found as they are no
longer present in the `scheduled` queues.
"""
FAIL_DEPS_ACROSS_MULTIPLE_TARGETS = (
    "DVSim cannot handle dependency fan-out across multiple targets."
)
FAIL_DEPS_ACROSS_NON_CONSECUTIVE_TARGETS = (
    "DVSim cannot handle dependencies that span non-consecutive (non-adjacent) targets."
)
FAIL_IF_NO_DEPS_WITHOUT_ALL_DEPS_NEEDED = """
Current DVSim has a strange behaviour where a job with no dependencies is dispatched if it is
marked as needing all its dependencies to pass, but fails (i.e. is killed) if it is marked as
*not* needing all of its dependencies.
"""
FAIL_DEP_OUT_OF_ORDER = """
DVSim cannot handle jobs given in an order that define dependencies and targets such that, to
resolve the jobs according to those dependencies, the targets must be processed in a different
order to the ordering of the jobs.
"""


# Default scheduler test timeout to handle infinite loops in the scheduler
DEFAULT_TIMEOUT = 0.5
SIGNAL_TEST_TIMEOUT = 2.5


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


class TestSchedulingStructure:
    """Unit tests for scheduling decisions related to the job specification structure.

    (i.e. the dependencies between jobs and the targets that jobs lie within).
    """

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize(
        "needs_all_passing",
        [
            True,
            pytest.param(
                False,
                marks=pytest.mark.xfail(reason=FAIL_IF_NO_DEPS_WITHOUT_ALL_DEPS_NEEDED),
            ),
        ],
    )
    def test_no_deps(fxt: Fxt, *, needs_all_passing: bool) -> None:
        """Tests scheduling of jobs without any listed dependencies."""
        job = job_spec_factory(fxt.tmp_path, needs_all_dependencies_passing=needs_all_passing)
        result = Scheduler([job], fxt.mock_launcher).run()
        _assert_result_status(result, 1)

    @staticmethod
    def _dep_test_case(
        fxt: Fxt,
        dep_list: dict[int, list[int]],
        *,
        all_passing: bool,
    ) -> Sequence[CompletedJobStatus]:
        """Run a simple dependency test, with 5 jobs where jobs 2 & 4 will fail."""
        jobs = make_many_jobs(
            fxt.tmp_path,
            5,
            needs_all_dependencies_passing=all_passing,
            interdeps=dep_list,
        )
        fxt.mock_ctx.set_config(jobs[2], MockJob(default_status=JobStatus.FAILED))
        fxt.mock_ctx.set_config(jobs[4], MockJob(default_status=JobStatus.FAILED))
        return Scheduler(jobs, fxt.mock_launcher).run()

    @staticmethod
    @pytest.mark.xfail(
        reason=FAIL_DEP_ON_MULTIPLE_TARGETS + " " + FAIL_IF_NO_DEPS_WITHOUT_ALL_DEPS_NEEDED
    )
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize(
        ("dep_list", "passes"),
        [
            ({0: [1]}, [0, 1, 3]),
            ({1: [2]}, [0, 3]),
            ({3: [2, 4]}, [0, 1]),
            ({3: [1, 2, 4]}, [0, 1, 3]),
            ({0: [1, 2, 3, 4]}, [0, 1, 3]),
        ],
    )
    def test_needs_any_dep(
        fxt: Fxt,
        dep_list: dict[int, list[int]],
        passes: list[int],
    ) -> None:
        """Tests scheduling of jobs with dependencies that don't need all passing."""
        result = TestSchedulingStructure._dep_test_case(fxt, dep_list, all_passing=False)
        assert_that(len(result), equal_to(5))
        for job in passes:
            assert_that(result[job].status, equal_to(JobStatus.PASSED))

    @staticmethod
    @pytest.mark.xfail(reason=FAIL_DEP_ON_MULTIPLE_TARGETS)
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize(
        ("dep_list", "passes"),
        [
            ({0: [1]}, [0, 1, 3]),
            ({1: [0, 3]}, [0, 1, 3]),
            ({3: [2]}, [0, 1]),
            ({0: [3, 4]}, [1, 3]),
            ({3: [0, 1, 2]}, [0, 1]),
            ({1: [1, 2, 3, 4]}, [0, 3]),
        ],
    )
    def test_needs_all_deps(
        fxt: Fxt,
        dep_list: dict[int, list[int]],
        passes: list[int],
    ) -> None:
        """Tests scheduling of jobs with dependencies that need all passing."""
        result = TestSchedulingStructure._dep_test_case(fxt, dep_list, all_passing=True)
        assert_that(len(result), equal_to(5))
        for job in passes:
            assert_that(result[job].status, equal_to(JobStatus.PASSED))

    @staticmethod
    @pytest.mark.xfail(
        reason="DVSim does not currently have logic to detect and error on"
        "dependency cycles within provided job specifications."
    )
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize(
        ("dep_list"),
        [
            {0: [1], 1: [0]},
            {0: [1], 1: [2], 2: [0]},
            {0: [1], 1: [2], 2: [3], 3: [4], 4: [0]},
            {0: [1, 2], 1: [2], 2: [3, 4, 0]},
            {0: [1, 2, 3, 4], 1: [2, 3, 4], 2: [3, 4], 3: [4], 4: [0]},
        ],
    )
    def test_dep_cycle(fxt: Fxt, dep_list: dict[int, list[int]]) -> None:
        """Test that the scheduler can detect and handle cycles in dependencies."""
        jobs = make_many_jobs(fxt.tmp_path, 5, interdeps=dep_list)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        # Expect that either we get an empty result, or at least some job failed
        # due to the cycle in dependencies.
        assert_that(len(result), any_of(equal_to(5), equal_to(0)))
        statuses = [c.status for c in result]
        if statuses:
            assert_that(
                statuses,
                any_of(has_item(JobStatus.FAILED), has_item(JobStatus.KILLED)),
            )

    @staticmethod
    @pytest.mark.xfail(
        reason=FAIL_DEP_ON_MULTIPLE_TARGETS + " " + FAIL_DEPS_ACROSS_MULTIPLE_TARGETS
    )
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize(
        ("dep_list"),
        [
            {0: [1, 2, 3, 4], 1: [2, 3, 4], 2: [3, 4], 3: [4]},
            {0: [1, 2], 4: [2, 3]},
            {0: [1], 1: [2], 2: [3], 3: [4]},
            {0: [1, 2, 3, 4], 1: [2], 3: [2, 4], 4: [2]},
        ],
    )
    def test_dep_resolution(fxt: Fxt, dep_list: dict[int, list[int]]) -> None:
        """Test that the scheduler can correctly resolve complex job dependencies."""
        jobs = make_many_jobs(fxt.tmp_path, 5, interdeps=dep_list)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 5)

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_deps_across_polls(fxt: Fxt) -> None:
        """Test that the scheduler can resolve multiple deps that complete at different times."""
        jobs = make_many_jobs(fxt.tmp_path, 4)
        # For now, define the end job separately so that we can put it in a different target
        # but keep the other jobs in the same target (to circumvent FAIL_DEP_ON_MULTIPLE_TARGETS).
        jobs.append(
            job_spec_factory(
                fxt.tmp_path,
                name="end",
                dependencies=[job.name for job in jobs],
                target="end_target",
            )
        )
        polls = [i * 5 for i in range(5)]
        for i in range(1, 5):
            fxt.mock_ctx.set_config(
                jobs[i],
                MockJob(
                    status_thresholds=[(0, JobStatus.DISPATCHED), (polls[i], JobStatus.PASSED)]
                ),
            )
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 5)
        # Sanity check that we did poll each job the correct number of times as well
        for i in range(1, 5):
            config = fxt.mock_ctx.get_config(jobs[i])
            if config is not None:
                assert_that(config.poll_count, equal_to(polls[i]))

    @staticmethod
    @pytest.mark.xfail(
        reason="DVSim currently implicitly assumes that job with/in other targets"
        " will be reachable (i.e. transitive) dependencies of jobs in the first target."
    )
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_multiple_targets(fxt: Fxt) -> None:
        """Test that the scheduler can handle jobs across many targets."""
        # Create 15 jobs across 5 targets (3 jobs per target), with no dependencies.
        jobs = make_many_jobs(fxt.tmp_path, 15, per_job=lambda i: {"target": f"target_{i // 3}"})
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 15)

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize("num_deps", range(2, 6))
    def test_cross_target_deps(fxt: Fxt, num_deps: int) -> None:
        """Test that the scheduler can handle dependencies across targets."""
        deps = {i: [i - 1] for i in range(1, num_deps)}
        jobs = make_many_jobs(fxt.tmp_path, num_deps, interdeps=deps, vary_targets=True)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, num_deps)

    @staticmethod
    @pytest.mark.xfail(reason=FAIL_DEP_ON_MULTIPLE_TARGETS)
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize("num_deps", range(2, 6))
    def test_dep_fan_in(fxt: Fxt, num_deps: int) -> None:
        """Test that job dependencies can fan-in from multiple other jobs."""
        num_jobs = num_deps + 1
        deps = {0: list(range(1, num_jobs))}
        jobs = make_many_jobs(fxt.tmp_path, num_jobs, interdeps=deps)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, num_jobs)

    @staticmethod
    @pytest.mark.xfail(reason=FAIL_DEPS_ACROSS_MULTIPLE_TARGETS)
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize("num_deps", range(2, 6))
    def test_dep_fan_out(fxt: Fxt, num_deps: int) -> None:
        """Test that job dependencies can fan-out to multiple other jobs."""
        num_jobs = num_deps + 1
        deps = {i: [num_deps] for i in range(num_deps)}
        jobs = make_many_jobs(fxt.tmp_path, num_jobs, interdeps=deps, vary_targets=True)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, num_jobs)

    @staticmethod
    @pytest.mark.xfail(reason=FAIL_DEPS_ACROSS_NON_CONSECUTIVE_TARGETS)
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_non_consecutive_targets(fxt: Fxt) -> None:
        """Test that jobs can have non-consecutive dependencies (deps in non-adjacent targets)."""
        jobs = make_many_jobs(fxt.tmp_path, 4, interdeps={3: [0]}, vary_targets=True)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 4)

    @staticmethod
    @pytest.mark.xfail(reason=FAIL_DEP_OUT_OF_ORDER)
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_target_out_of_order(fxt: Fxt) -> None:
        """Test that the scheduler can handle targets being given out-of-dependency-order."""
        jobs = make_many_jobs(fxt.tmp_path, 4, interdeps={1: [0], 2: [3]}, vary_targets=True)
        # First test jobs 0 and 1 (0 -> 1). Then test jobs 2 and 3 (2 <- 3).
        for order in (jobs[:2], jobs[2:]):
            result = Scheduler(order, fxt.mock_launcher).run()
            _assert_result_status(result, 2)

    # TODO: it isn't clear if this is a feature that DVSim should actually support.
    # If Job specifications can form any DAG where targets are essentially just vertex
    # labels/groups, then it makes sense that we can support a target-/layer-annotated
    # specification with "bi-directional" edges. If layers are structural and intended
    # to be monotonically increasing, this test should be changed / removed. For now,
    # we test as if the former is the intended behaviour.
    @staticmethod
    @pytest.mark.xfail(reason="DVSim cannot currently handle this case.")
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_bidirectional_deps(fxt: Fxt) -> None:
        """Test that the scheduler handles bidirectional cross-target deps."""
        # job_0 (target_0) -> job_1 (target_1) -> job_2 (target_0)
        targets = ["target_0", "target_1", "target_0"]
        jobs = make_many_jobs(
            fxt.tmp_path, 3, interdeps={0: [1], 1: [2]}, per_job=lambda i: {"target": targets[i]}
        )
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 3)

    @staticmethod
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    @pytest.mark.parametrize("error_status", [JobStatus.FAILED, JobStatus.KILLED])
    def test_dep_fail_propagation(fxt: Fxt, error_status: JobStatus) -> None:
        """Test that failures in job dependencies propagate."""
        # Note: job order is due to working around FAIL_DEP_OUT_OF_ORDER.
        deps = {i: [i - 1] for i in range(1, 5)}
        jobs = make_many_jobs(fxt.tmp_path, n=5, interdeps=deps, vary_targets=True)
        fxt.mock_ctx.set_config(jobs[0], MockJob(default_status=error_status))
        result = Scheduler(jobs, fxt.mock_launcher).run()
        assert_that(len(result), equal_to(5))
        # The job that we configured to error should show the error status
        assert_that(result[0].status, equal_to(error_status))
        # All other jobs should be "KILLED" due to failure propagation
        _assert_result_status(result[1:], 4, expected=JobStatus.KILLED)


class TestSchedulingPriority:
    """Unit tests for scheduler decisions related to job/target weighting/priority."""

    @staticmethod
    @pytest.mark.xfail(
        reason=FAIL_DEPS_ACROSS_MULTIPLE_TARGETS + " " + FAIL_DEPS_ACROSS_NON_CONSECUTIVE_TARGETS
    )
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_job_priority(fxt: Fxt) -> None:
        """Test that jobs across targets are prioritised according to their weight."""
        start_job = job_spec_factory(fxt.tmp_path, name="start")
        weighted_jobs = make_many_jobs(
            fxt.tmp_path,
            n=6,
            per_job=lambda n: {"weight": n + 1},
            dependencies=["start"],
            vary_targets=True,
        )
        jobs = [start_job, *weighted_jobs]
        by_weight_dec = [
            j.name for j in sorted(weighted_jobs, key=lambda job: job.weight, reverse=True)
        ]
        # Set max parallel = 1 so that order dispatched becomes the priority order
        # With max parallel > 1, jobs of many priorities are dispatched "at once".
        fxt.mock_launcher.max_parallel = 1
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 6)
        assert_that(fxt.mock_ctx.order_started, equal_to([start_job, *by_weight_dec]))

    @staticmethod
    @pytest.mark.xfail(reason="DVSim does not handle zero weights.")
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_zero_weight(fxt: Fxt) -> None:
        """Test that the scheduler can handle the case where jobs have a total weight of zero."""
        jobs = make_many_jobs(fxt.tmp_path, 5, weight=0)
        result = Scheduler(jobs, fxt.mock_launcher).run()
        # TODO: not clear if this should evenly distribute and succeed, or error.
        _assert_result_status(result, 5)

    @staticmethod
    @pytest.mark.xfail(
        reason=FAIL_DEPS_ACROSS_MULTIPLE_TARGETS + " " + FAIL_DEPS_ACROSS_NON_CONSECUTIVE_TARGETS
    )
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    def test_blocked_weight_starvation(fxt: Fxt) -> None:
        """Test that high weight jobs without fulfilled deps do not block lower weight jobs."""
        # All jobs spawn from a start job.
        # There is one chain "start -> long_blocker -> high" where we have a high weight job
        # blocked by some blocker that takes a long time.
        # There are then 5 other jobs that depend on "start -> short_blocker -> low", which
        # are low weight jobs blocked by some blocker that takes a short time.
        start_job = job_spec_factory(fxt.tmp_path, name="start")
        short_blocker = job_spec_factory(fxt.tmp_path, name="short", dependencies=["start"])
        long_blocker = job_spec_factory(fxt.tmp_path, name="long", dependencies=["start"])
        high = job_spec_factory(fxt.tmp_path, name="high", dependencies=["long"], weight=1000000)
        jobs = [start_job, short_blocker, long_blocker, high]
        jobs += make_many_jobs(
            fxt.tmp_path,
            n=5,
            weight=1,
            dependencies=["short"],
            vary_targets=True,
        )
        # The blockers should take a bit of time, to let the non-blocked jobs progress
        fxt.mock_ctx.set_config(
            short_blocker,
            MockJob(status_thresholds=[(0, JobStatus.DISPATCHED), (1, JobStatus.PASSED)]),
        )
        fxt.mock_ctx.set_config(
            long_blocker,
            MockJob(status_thresholds=[(0, JobStatus.DISPATCHED), (5, JobStatus.PASSED)]),
        )
        result = Scheduler(jobs, fxt.mock_launcher).run()
        _assert_result_status(result, 8)
        # We expect that the high weight job should have been scheduled last, since
        # it was blocked by the blocker (unlike all the other lower weight jobs)
        assert_that(fxt.mock_ctx.order_started[0], equal_to(start_job))
        assert_that(fxt.mock_ctx.order_started[-1], equal_to(high))

    # TODO: we do not currently test the logic to schedule multiple queued jobs per target
    # across different targets based on the weights of those jobs/targets, because this
    # will require the test to be quite complex and specific to the intricacies of the
    # current DVSim scheduler due to the current implementation. Due to only one successor
    # in another target being discovered at once, we must carefully construct a dependency
    # tree of jobs with specially modelled delays which relies on this implementation
    # detail. Instead, for now at least, we leave this untested.
    #
    # Note also that DVSim currently assumes weights within a target are constant,
    # which may not be the case with the current JobSpec model.


class TestSignals:
    """Integration tests for the signal-handling of the scheduler."""

    @staticmethod
    def _run_signal_test(tmp_path: Path, sig: int, *, repeat: bool, long_poll: bool) -> None:
        """Test that the scheduler can be gracefully killed by incoming signals."""

        # We cannot access the fixtures from the separate process, so define a minimal
        # mock launcher class here.
        class SignalTestMockLauncher(MockLauncher):
            pass

        mock_ctx = MockLauncherContext()
        SignalTestMockLauncher.mock_context = mock_ctx
        SignalTestMockLauncher.max_parallel = 2
        if long_poll:
            # Set a very long poll frequency to be sure that the signal interrupts the
            # scheduler from a sleep if configured with infrequent polls.
            SignalTestMockLauncher.poll_freq = 360000

        jobs = make_many_jobs(tmp_path, 3, ensure_paths_exist=True)
        # When testing non-graceful exits, we make `kill()` hang and send two signals.
        kill_time = None if not repeat else 100.0
        # Job 0 is permanently "dispatched", it never completes.
        mock_ctx.set_config(
            jobs[0], MockJob(default_status=JobStatus.DISPATCHED, kill_time=kill_time)
        )
        # Job 1 will pass, but after a long time (a large number of polls).
        mock_ctx.set_config(
            jobs[1],
            MockJob(
                status_thresholds=[(0, JobStatus.DISPATCHED), (1000000000, JobStatus.PASSED)],
                kill_time=kill_time,
            ),
        )
        # Job 2 is also permanently "dispatched", but will never run due to the
        # max paralellism limit on the launcher. It will instead be cancelled.
        mock_ctx.set_config(
            jobs[2], MockJob(default_status=JobStatus.DISPATCHED, kill_time=kill_time)
        )
        scheduler = Scheduler(jobs, SignalTestMockLauncher)

        def _get_signal(sig_received: int, _: FrameType | None) -> None:
            assert_that(sig_received, equal_to(sig))
            assert_that(repeat)
            sys.exit(0)

        if repeat:
            # Sending multiple signals will call the regular signal handler
            # which will kill the process. Register a mock handler to stop
            # that happening and we can check that we "killed the process".
            signal(sig, _get_signal)

        def _send_signals() -> None:
            # Give time for the handler to be installed and jobs to dispatch
            # and for the main loop to enter a sleep/wait.
            wait_time = 0.1
            time.sleep(wait_time)
            pid = os.getpid()
            os.kill(pid, sig)
            if repeat:
                time.sleep(wait_time)
                os.kill(pid, sig)

        # Send signals from a separate thread
        threading.Thread(target=_send_signals).start()
        result = scheduler.run()

        # If we didn't reach `_get_signal`, this should be a graceful exit
        assert_that(not repeat)
        _assert_result_status(result, 3, expected=JobStatus.KILLED)

    @staticmethod
    @pytest.mark.xfail(
        reason="This test passes ~95 percent of the time, but the logging & threading primitive"
        "logic used in the signal handler are not async-signal-safe and thus may deadlock,"
        "causing the process to hang and time out instead.",
        strict=False,
    )
    @pytest.mark.parametrize("long_poll", [False, True])
    @pytest.mark.parametrize(("sig", "repeat"), [(SIGTERM, False), (SIGINT, False), (SIGINT, True)])
    def test_signal_kill(tmp_path: Path, *, sig: int, repeat: bool, long_poll: bool) -> None:
        """Test that the scheduler can be gracefully killed by incoming signals."""
        # We must test in a separate process, otherwise pytest interprets the SIGINT and SIGTERM
        # signals using its own signal handlers as signals to quit pytest itself...
        proc = multiprocessing.Process(
            target=TestSignals._run_signal_test,
            args=(tmp_path, sig),
            kwargs={"repeat": repeat, "long_poll": long_poll},
        )
        proc.start()
        proc.join(timeout=SIGNAL_TEST_TIMEOUT)
        if proc.is_alive():
            proc.kill()  # SIGKILL instead of SIGINT or SIGTERM
            proc.join()
            pytest.fail("Scheduler hung and was terminated")
        assert_that(proc.exitcode, equal_to(0))
