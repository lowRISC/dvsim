# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job scheduler."""

import asyncio
import heapq
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from signal import SIGINT, SIGTERM, getsignal, signal
from types import FrameType
from typing import Any, TypeAlias

from dvsim.job.data import CompletedJobStatus, JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.data import JobCompletionEvent, JobHandle
from dvsim.scheduler.resources import ResourceManager

__all__ = (
    "JobPriorityFn",
    "JobRecord",
    "OnJobStatusChangeCb",
    "OnRunEndCb",
    "OnRunStartCb",
    "OnSchedulerKillCb",
    "Priority",
    "Scheduler",
)


@dataclass
class JobRecord:
    """Mutable runtime representation of a scheduled job, used in the scheduler."""

    spec: JobSpec
    backend_key: str  # either spec.backend, or the default backend if not given

    status: JobStatus = JobStatus.SCHEDULED
    status_info: JobStatusInfo | None = None

    remaining_deps: int = 0
    passing_deps: int = 0
    dependents: list[str] = field(default_factory=list)
    kill_requested: bool = False

    handle: JobHandle | None = None


# Function to assign a priority to a given job specification. The returned priority should be
# some lexicographically orderable type. Jobs with higher priority are scheduled first.
Priority: TypeAlias = int | float | Sequence[int | float]
JobPriorityFn: TypeAlias = Callable[[JobRecord], Priority]

# Callbacks for observers, for when the scheduler run starts and stops
OnRunStartCb: TypeAlias = Callable[[], None]
OnRunEndCb: TypeAlias = Callable[[], None]

# Callbacks for observers, for when a job status changes in the scheduler
# The arguments are: (job spec, old status, new status).
OnJobStatusChangeCb: TypeAlias = Callable[[JobSpec, JobStatus, JobStatus], None]

# Callbacks for observers, for when the scheduler receives a kill signal (termination).
OnSchedulerKillCb: TypeAlias = Callable[[], None]


# Standard context messages used for killed/failed jobs in the scheduler.
FAILED_DEP = JobStatusInfo(
    message="Job cancelled because one of its dependencies failed or was killed."
)
ALL_FAILED_DEP = JobStatusInfo(
    message="Job cancelled because all of its dependencies failed or were killed."
)
KILLED_SCHEDULED = JobStatusInfo(
    message="Job cancelled because one of its dependencies was killed."
)
KILLED_QUEUED = JobStatusInfo(message="Job killed whilst waiting to begin execution.")
KILLED_RUNNING_SIGINT = JobStatusInfo(
    message="Job killed by a SIGINT signal to the scheduler whilst executing."
)
KILLED_RUNNING_SIGTERM = JobStatusInfo(
    message="Job killed by a SIGTERM signal to the scheduler whilst executing."
)


class Scheduler:
    """Event-driven job scheduler that schedules and runs a DAG of job specifications."""

    def __init__(  # noqa: PLR0913
        self,
        jobs: Iterable[JobSpec],
        backends: Mapping[str, RuntimeBackend],
        default_backend: str,
        *,
        max_parallelism: int | None = None,
        resource_manager: ResourceManager | None = None,
        priority_fn: JobPriorityFn | None = None,
        coalesce_window: float | None = 0.001,
    ) -> None:
        """Construct a new scheduler to run a DAG of jobs.

        Args:
            jobs: The DAG of jobs to run. A sequence of job specifications, where the DAG is
              defined by the job IDs and job dependency lists.
            backends: The mapping (name -> backend) of backends available to the scheduler.
            default_backend: The name of the default backend to use if not specified by a job.
            max_parallelism: The maximum number of jobs that the scheduler is allowed to dispatch
              at once, across all backends. The default value of `None` indicates no upper limit.
            resource_manager: The scheduler's resource manager, through which per-job resources
              are allocated to enforce additional limits on scheduler parallelism.
            priority_fn: A function to calculate the priority of a given job. If no function is
              given, this defaults to using the job's weight.
            coalesce_window: If specified, the time in seconds to wait on receiving a job
              completion, to give a short amount of time to allow other batched completion events
              to arrive in the queue. This lets us batch scheduling more frequently for a little
              extra cost. Defaults to 1 millisecond, and can be disabled by giving `None`.

        """
        if max_parallelism is not None and max_parallelism <= 0:
            err = f"max_parallelism must be some positive integer or None, not {max_parallelism}"
            raise ValueError(err)
        if default_backend not in backends:
            err = f"Default backend '{default_backend}' is not in the mapping of given backends"
            raise ValueError(err)
        if coalesce_window is not None and coalesce_window < 0.0:
            raise ValueError("coalesce_window must be None or some non-negative number")

        # Configuration of the scheduler's behaviour
        self._backends = dict(backends)
        self._default_backend = default_backend
        self._max_parallelism = max_parallelism
        self._resources = resource_manager
        self._priority_fn = priority_fn or self._default_priority
        self._coalesce_window = coalesce_window

        # Internal data structures and indexes to track running jobs.
        self._jobs: dict[str, JobRecord] = {}
        self._ready_heap: list[tuple[Priority, str]] = []
        self._running: set[str] = set()
        self._running_per_backend: dict[str, int] = dict.fromkeys(backends, 0)
        self._event_queue: asyncio.Queue[Iterable[JobCompletionEvent]] = asyncio.Queue()

        # Internal flags and signal handling
        self._shutdown_signal: int | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._original_sigint_handler: Any = None
        self._shutdown_started = False

        # Registered callbacks from observers
        self._on_run_start: list[OnRunStartCb] = []
        self._on_run_end: list[OnRunEndCb] = []
        self._on_job_status_change: list[OnJobStatusChangeCb] = []
        self._on_kill_signal: list[OnSchedulerKillCb] = []

        self._jobs = self.build_graph(jobs, self._backends, self._default_backend)

    def add_run_start_callback(self, cb: OnRunStartCb) -> None:
        """Register an observer to notify when the scheduler run is started."""
        self._on_run_start.append(cb)

    def add_run_end_callback(self, cb: OnRunEndCb) -> None:
        """Register an observer to notify when the scheduler run ends."""
        self._on_run_end.append(cb)

    def add_job_status_change_callback(self, cb: OnJobStatusChangeCb) -> None:
        """Register an observer to notify when the status of a job in the scheduler changes."""
        self._on_job_status_change.append(cb)

    def add_kill_signal_callback(self, cb: OnSchedulerKillCb) -> None:
        """Register an observer to notify when the scheduler is killed by some signal."""
        self._on_kill_signal.append(cb)

    def _default_priority(self, job: JobRecord) -> Priority:
        """Prioritizes jobs according to their weight. The default prioritization method."""
        return job.spec.weight

    @staticmethod
    def build_graph(
        specs: Iterable[JobSpec], backends: Iterable[str], default_backend: str
    ) -> dict[str, JobRecord]:
        """Build the job dependency graph and validate the DAG structure.

        Args:
            specs: The list of job specifications that comprise the DAG.
            backends: The list of defined backend (names) that can be used by jobs.
            default_backend: The backend that is used by default if not defined by a spec.

        Returns:
            A (validated) dict mapping job IDs to records representing the graph.

        """
        # Build an index of runtime job records, and check for duplicates
        job_graph: dict[str, JobRecord] = {}
        for spec in specs:
            if spec.id in job_graph:
                log.warning("Duplicate job ID '%s'", spec.id)
                # TODO: when we're sure it's ok, change the behaviour to error on duplicate jobs
                #  : err = f"Duplicate job ID '{spec.id}'"
                #  : raise ValueError(err)
                # Instead, silently ignore it for now to match the original scheduler behaviour
                continue
            if spec.backend is not None and spec.backend not in backends:
                err = f"Unknown job backend '{spec.backend}'"
                raise ValueError(err)
            backend_name = default_backend if spec.backend is None else spec.backend
            job_graph[spec.id] = JobRecord(spec=spec, backend_key=backend_name)

        # Build a graph from the adjacency list formed by the spec dependencies
        for job in job_graph.values():
            job.remaining_deps = len(job.spec.dependencies)
            for dep in job.spec.dependencies:
                if dep not in job_graph:
                    err = f"Unknown job dependency '{dep}' for job {job.spec.id}"
                    raise ValueError(err)
                job_graph[dep].dependents.append(job.spec.id)

        # Validate that there are no cycles in the given graph.
        Scheduler.validate_acyclic(job_graph)

        return job_graph

    @staticmethod
    def validate_acyclic(job_graph: Mapping[str, JobRecord]) -> None:
        """Validate that the given job digraph is acyclic via Kahn's Algorithm."""
        indegree = {job: record.remaining_deps for job, record in job_graph.items()}
        job_queue = [job for job, degree in indegree.items() if degree == 0]
        num_visited = 0

        while job_queue:
            job = job_queue.pop()
            num_visited += 1
            for dep in job_graph[job].dependents:
                indegree[dep] -= 1
                if indegree[dep] == 0:
                    job_queue.append(dep)

        if num_visited != len(job_graph):
            raise ValueError("The given JobSpec graph contains a dependency cycle.")

    def _notify_run_started(self) -> None:
        """Notify any observers that the scheduler run has started."""
        for cb in self._on_run_start:
            cb()

    def _notify_run_finished(self) -> None:
        """Notify any observers that the scheduler run has finished."""
        for cb in self._on_run_end:
            cb()

    def _notify_kill_signal(self) -> None:
        """Notify any observers that the scheduler received a kill signal."""
        for cb in self._on_kill_signal:
            cb()

    def _change_job_status(
        self, job: JobRecord, new_status: JobStatus, info: JobStatusInfo | None = None
    ) -> JobStatus:
        """Change a job's runtime status, storing an optionally associated reason.

        Notifies any status change observers of the change, and returns the previous status.
        """
        old_status = job.status
        if old_status == new_status:
            return old_status

        job.status = new_status
        job.status_info = info

        if new_status != JobStatus.RUNNING:
            log.log(
                log.ERROR if new_status in (JobStatus.FAILED, JobStatus.KILLED) else log.VERBOSE,
                "Status change to [%s: %s] for %s",
                new_status.shorthand,
                new_status.name.capitalize(),
                job.spec.full_name,
            )

        for cb in self._on_job_status_change:
            cb(job.spec, old_status, new_status)

        return old_status

    def _mark_job_ready(self, job: JobRecord) -> None:
        """Mark a given job in the scheduler as ready to execute (all dependencies completed)."""
        if job.status != JobStatus.SCHEDULED:
            msg = f"_mark_job_ready only applies to 'SCHEDULED' jobs (not '{job.status.name}')."
            raise RuntimeError(msg)

        self._change_job_status(job, JobStatus.QUEUED)
        # heapq is a min heap, so push (-priority) instead of (priority).
        priority = self._priority_fn(job)
        priority = priority if isinstance(priority, Sequence) else (priority,)
        neg_priority: Priority = tuple(-x for x in priority)
        heapq.heappush(self._ready_heap, (neg_priority, job.spec.id))

    def _mark_job_running(self, job: JobRecord) -> None:
        """Mark a given job in the scheduler as running. Assumes already removed from the heap."""
        if job.spec.id in self._running:
            raise RuntimeError("_mark_job_running called on a job that was already running.")

        self._change_job_status(job, JobStatus.RUNNING)
        self._running.add(job.spec.id)
        self._running_per_backend[job.backend_key] += 1

    def _mark_job_completed(
        self, job: JobRecord, status: JobStatus, reason: JobStatusInfo | None
    ) -> None:
        """Mark a given job in the scheduler as completed, having reached some terminal state."""
        if not status.is_terminal:
            err = f"_mark_job_completed called with non-terminal status '{status.name}'"
            raise RuntimeError(err)
        if job.status.is_terminal:
            return

        # If the scheduler requested to kill the job, override the failure reason.
        if job.kill_requested:
            reason = (
                KILLED_RUNNING_SIGINT if self._shutdown_signal == SIGINT else KILLED_RUNNING_SIGTERM
            )
        self._change_job_status(job, status, reason)

        # If the job was running, mark it as no longer running.
        if job.spec.id in self._running:
            self._running.remove(job.spec.id)
            self._running_per_backend[job.backend_key] -= 1
            if self._resources and job.spec.resources:
                self._resources.release(job.spec.resources)

        # Update dependents (jobs that depend on this job), propagating failures if needed.
        self._update_completed_job_deps(job)

    def _update_completed_job_deps(self, job: JobRecord) -> None:
        """Update the dependencies of a completed job, scheduling/killing deps where necessary."""
        for dep_id in job.dependents:
            dep = self._jobs[dep_id]

            # Update dependency tracking counts in the dependency records
            dep.remaining_deps -= 1
            if job.status == JobStatus.PASSED:
                dep.passing_deps += 1

            # Propagate kill signals on shutdown
            if self._shutdown_signal is not None:
                self._mark_job_completed(dep, JobStatus.KILLED, KILLED_SCHEDULED)
                continue

            # Handle dependency management and marking dependents as ready
            if dep.remaining_deps == 0 and dep.status == JobStatus.SCHEDULED:
                if dep.spec.needs_all_dependencies_passing:
                    if dep.passing_deps == len(dep.spec.dependencies):
                        self._mark_job_ready(dep)
                    else:
                        self._mark_job_completed(dep, JobStatus.KILLED, FAILED_DEP)
                elif dep.passing_deps > 0:
                    self._mark_job_ready(dep)
                else:
                    self._mark_job_completed(dep, JobStatus.KILLED, ALL_FAILED_DEP)

    async def run(self) -> list[CompletedJobStatus]:
        """Run all scheduled jobs to completion (unless terminated) and return the results."""
        # Check if we know about all the resources defined by the given jobs, and whether
        # initial resource availability can (independently) satisfy all jobs' needs.
        # This is an error if we know we are using static resources, and a warning otherwise.
        if self._resources:
            specs = [job.spec for job in self._jobs.values()]
            await self._resources.validate_jobs(specs)

        self._install_signal_handlers()

        for backend in self._backends.values():
            backend.attach_completion_callback(self._submit_job_completion)

        self._notify_run_started()

        # Before entering the main loop, mark jobs with 0 remaining deps as ready to run.
        for job in self._jobs.values():
            if job.remaining_deps == 0:
                self._mark_job_ready(job)

        try:
            await self._main_loop()
        finally:
            self._notify_run_finished()

        return [
            CompletedJobStatus(
                name=job.spec.name,
                job_type=job.spec.job_type,
                seed=job.spec.seed,
                block=job.spec.block,
                tool=job.spec.tool,
                workspace_cfg=job.spec.workspace_cfg,
                full_name=job.spec.full_name,
                qual_name=job.spec.qual_name,
                target=job.spec.target,
                log_path=job.spec.log_path,
                job_runtime=job.handle.job_runtime.with_unit("s").get()[0]
                if job.handle is not None
                else 0.0,
                simulated_time=job.handle.simulated_time.with_unit("us").get()[0]
                if job.handle is not None
                else 0.0,
                status=job.status,
                fail_msg=job.status_info,
            )
            for job in self._jobs.values()
        ]

    def _install_signal_handlers(self) -> None:
        """Install the SIGINT/SIGTERM signal handlers to trigger graceful shutdowns."""
        self._shutdown_signal = None
        self._shutdown_event = asyncio.Event()
        self._original_sigint_handler = getsignal(SIGINT)
        self._shutdown_started = False
        loop = asyncio.get_running_loop()

        def _handler(signum: int, _frame: FrameType | None) -> None:
            if self._shutdown_signal is None and self._shutdown_event:
                self._shutdown_signal = signum
                loop.call_soon_threadsafe(self._shutdown_event.set)

            # Restore the original SIGINT handler so a second Ctrl-C terminates immediately
            if signum == SIGINT:
                signal(SIGINT, self._original_sigint_handler)

        loop.add_signal_handler(SIGINT, lambda: _handler(SIGINT, None))
        loop.add_signal_handler(SIGTERM, lambda: _handler(SIGTERM, None))

    async def _submit_job_completion(self, events: Iterable[JobCompletionEvent]) -> None:
        """Notify the scheduler that a batch of jobs have been completed."""
        try:
            self._event_queue.put_nowait(events)
        except asyncio.QueueShutDown as e:
            msg = "Scheduler event queue shutdown earlier than expected?"
            raise RuntimeError(msg) from e
        except asyncio.QueueFull:
            log.critical("Scheduler event queue full despite being infinitely sized?")

    async def _main_loop(self) -> None:
        """Run the main scheduler loop.

        Tries to schedule any ready jobs if there is available capacity, and then waits for any job
        completions (or a shutdown signal). This continues in a loop until all jobs have been either
        executed or killed (e.g. via a shutdown signal).
        """
        if self._shutdown_event is None:
            raise RuntimeError("Expected signal handlers to be installed before running main loop")

        job_completion_task = asyncio.create_task(self._event_queue.get())
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())

        try:
            while True:
                await self._schedule_ready_jobs()

                if not self._running:
                    if not self._ready_heap:
                        break
                    # This case (nothing running, but jobs still pending in the queue) can happen
                    # if backends fail to schedule any jobs (e.g. the backend is temporarily busy).
                    continue

                # Wait for any job to complete, or for a shutdown signal
                try:
                    done, _ = await asyncio.wait(
                        (job_completion_task, shutdown_task),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                except asyncio.QueueShutDown as e:
                    msg = "Scheduler event queue shutdown earlier than expected?"
                    raise RuntimeError(msg) from e

                if shutdown_task in done:
                    self._shutdown_event.clear()
                    shutdown_task = asyncio.create_task(self._shutdown_event.wait())
                    await self._handle_exit_signal()
                    continue

                completions = await self._drain_completions(job_completion_task)
                job_completion_task = asyncio.create_task(self._event_queue.get())

                for event in completions:
                    job = self._jobs[event.spec.id]
                    self._mark_job_completed(job, event.status, event.reason)
        finally:
            job_completion_task.cancel()
            shutdown_task.cancel()

    async def _drain_completions(self, completion_task: asyncio.Task) -> list[JobCompletionEvent]:
        """Drain batched completions from the queue, optionally coalescing batched events."""
        events = list(completion_task.result())

        # Coalesce nearby completions by waiting for a very short time
        if self._coalesce_window is not None:
            await asyncio.sleep(self._coalesce_window)

        # Drain any more completion events from the event queue
        try:
            while True:
                events.extend(self._event_queue.get_nowait())
        except asyncio.QueueEmpty:
            return events
        except asyncio.QueueShutDown as e:
            msg = "Scheduler event queue shutdown earlier than expected?"
            raise RuntimeError(msg) from e

    async def _handle_exit_signal(self) -> None:
        """Attempt to gracefully shutdown as a result of a triggered exit signal."""
        if self._shutdown_started:
            return
        self._shutdown_started = True

        signal_name = "SIGTERM" if self._shutdown_signal == SIGTERM else "SIGINT"
        log.info("Received %s signal. Exiting gracefully", signal_name)
        if self._shutdown_signal == SIGINT:
            log.info(
                "Send another to force immediate quit (but you may need to manually "
                "kill some child processes)."
            )

        self._notify_kill_signal()

        # Mark any jobs that are currently running as jobs we should kill.
        # Collect jobs to kill in a dict, grouped per backend, for batched killing.
        to_kill: dict[str, list[JobHandle]] = defaultdict(list)

        for job_id in self._running:
            job = self._jobs[job_id]
            if job.handle is None:
                raise RuntimeError("Running job is missing an associated handle.")
            job.kill_requested = True
            to_kill[job.backend_key].append(job.handle)

        # Asynchronously dispatch backend kill tasks whilst we update scheduler internals.
        # Jobs that depend on these jobs will then be transitively killed before they start.
        kill_tasks: list[asyncio.Task] = []
        for backend_name, handles in to_kill.items():
            backend = self._backends[backend_name]
            kill_tasks.append(asyncio.create_task(backend.kill_many(handles)))

        # Kill any ready (but not running jobs), so that they don't get scheduled.
        while self._ready_heap:
            _, job_id = heapq.heappop(self._ready_heap)
            job = self._jobs[job_id]
            self._mark_job_completed(job, JobStatus.KILLED, KILLED_QUEUED)

        if kill_tasks:
            await asyncio.gather(*kill_tasks, return_exceptions=True)

    async def _get_jobs_to_launch(
        self, available_slots: int
    ) -> dict[str, list[tuple[Priority, JobRecord]]]:
        """Get the sets of jobs to try and launch at this moment.

        Returns a mapping of backend names to the lists of jobs to launch for that backend,
        where jobs are defined by their priority value and record.
        """
        # Collect jobs to launch in a dict, grouped per backend, for batched launching.
        to_launch: dict[str, list[tuple[Priority, JobRecord]]] = defaultdict(list)
        blocked: list[tuple[Priority, str]] = []
        slots_used = 0

        while self._ready_heap and slots_used < available_slots:
            neg_priority, job_id = heapq.heappop(self._ready_heap)
            job = self._jobs[job_id]
            backend = self._backends[job.backend_key]
            running_on_backend = self._running_per_backend[job.backend_key] + len(
                to_launch[job.backend_key]
            )

            # Check that we can launch the job whilst respecting backend parallelism limits
            if backend.max_parallelism and running_on_backend >= backend.max_parallelism:
                blocked.append((neg_priority, job_id))
                continue

            # Check we have the resources to run the job, and acquire them if so.
            if (
                self._resources
                and job.spec.resources
                and not await self._resources.try_allocate(job.spec.resources)
            ):
                blocked.append((neg_priority, job_id))
                continue

            to_launch[job.backend_key].append((neg_priority, job))
            slots_used += 1

        # Requeue any blocked jobs.
        for entry in blocked:
            heapq.heappush(self._ready_heap, entry)

        # If nothing is running and nothing was scheduled to run, there must not be
        # enough resources to run any jobs. Warn the user.
        if blocked and not self._running and slots_used == 0:
            log.warning(
                "All queued jobs cannot be scheduled due to resource limits, despite no jobs "
                "currently being executed."
            )

        return to_launch

    async def _schedule_ready_jobs(self) -> None:
        """Attempt to schedule ready jobs whilst respecting scheduler & backend parallelism."""
        # Find out how many jobs we can dispatch according to the scheduler's parallelism limit
        available_slots = (
            self._max_parallelism - len(self._running)
            if self._max_parallelism
            else len(self._ready_heap)
        )
        if available_slots <= 0:
            return

        to_launch = await self._get_jobs_to_launch(available_slots)

        # Launch the selected jobs in batches per backend
        launch_tasks = []
        for backend_name, jobs in to_launch.items():
            backend = self._backends[backend_name]
            job_specs = [job.spec for _, job in jobs]
            log.verbose(
                "[%s]: Dispatching jobs: %s",
                backend_name,
                ", ".join(job.full_name for job in job_specs),
            )
            launch_tasks.append(backend.submit_many(job_specs))

        results = await asyncio.gather(*launch_tasks)

        # Mark jobs running, and requeue any jobs that failed to launch
        for jobs, handles in zip(to_launch.values(), results, strict=True):
            for neg_priority, job in jobs:
                handle = handles.get(job.spec.id)
                if handle is None:
                    log.verbose("[%s]: Requeuing job '%s'", job.spec.target, job.spec.full_name)
                    heapq.heappush(self._ready_heap, (neg_priority, job.spec.id))
                    if self._resources and job.spec.resources:
                        self._resources.release(job.spec.resources)
                    continue

                job.handle = handle
                self._mark_job_running(job)
