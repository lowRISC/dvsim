# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Schedule runner."""

from collections.abc import Iterable

from dvsim import instrumentation
from dvsim.job.data import CompletedJobStatus, JobSpec
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.fake import FakePolicy, FakeRuntimeBackend
from dvsim.runtime.registry import backend_registry
from dvsim.scheduler.core import Scheduler
from dvsim.scheduler.log_manager import LogManager
from dvsim.scheduler.resources import (
    ResourceManager,
    ResourceMapping,
    StaticResourceProvider,
    UnknownResourcePolicy,
)
from dvsim.scheduler.status_printer import create_status_printer

__all__ = (
    "build_default_scheduler_backend",
    "run_scheduler",
)


def build_default_scheduler_backend(
    *,
    fake_policy: FakePolicy,
) -> RuntimeBackend:
    """Build a runtime backend.

    Args:
        fake_policy: policy for generating fake data if using the fake backend

    Returns:
        Runtime backend to use with the scheduler.

    """
    # Create the runtime backends. TODO: support multiple runtime backends at once
    default_backend = backend_registry.create(name=None)

    # If we're using the fake backend, tell it *how* to fake jobs for this flow.
    if isinstance(default_backend, FakeRuntimeBackend):
        default_backend.attach_fake_policy(fake_policy)

    return default_backend


def build_resource_manager(
    *,
    resource_limits: ResourceMapping,
    missing_policy: UnknownResourcePolicy,
) -> ResourceManager | None:
    """Build a resource manager for use with the scheduler and validate the given jobs' resources.

    Args:
        resource_limits: The list of static resource limits to impose on the scheduler.
        missing_policy: How to handle requested job resources without any defined limits.

    """
    if not resource_limits and missing_policy == UnknownResourcePolicy.IGNORE:
        return None

    provider = StaticResourceProvider(resource_limits)
    return ResourceManager(provider, missing_policy)


async def run_scheduler(
    *,
    jobs: Iterable[JobSpec],
    max_parallel: int,
    interactive: bool,
    backend: RuntimeBackend,
    resource_manager: ResourceManager | None,
) -> list[CompletedJobStatus]:
    """Run the scheduler with the given set of job specifications.

    Args:
        jobs: jobs to schedule
        max_parallel: number of max parallel jobs to run
        interactive: run the tool in interactive mode?
        backend: the scheduler backend to use
        resource_manager: the scheduler resource manager to use, if any.

    Returns:
        List of completed job status objects.

    """
    max_timeout = max((job.timeout_mins for job in jobs if job.timeout_mins), default=0)

    # Convert to list so that first use doesn't consume the Iterable
    jobs = list(jobs)

    scheduler = Scheduler(
        jobs=jobs,
        backends={backend.name: backend},
        default_backend=backend.name,
        max_parallelism=max_parallel,
        resource_manager=resource_manager,
        # The scheduler prioritizes jobs in (lexicographically) decreasing order based on
        # the given `priority_fn`. We hence define a prioritization scheme that prioritizes
        # first by decreasing weight, then by decreasing timeout, and finally by the decreasing
        # number of jobs that depend on this job.
        priority_fn=lambda job: (
            job.spec.weight,
            job.spec.timeout_mins or max_timeout + 1,
            len(job.dependents),
        ),
    )

    if not interactive:
        status_printer = create_status_printer(jobs)

        # Add status printer hooks
        scheduler.add_run_start_callback(status_printer.start)
        scheduler.add_job_status_change_callback(status_printer.update_status)
        scheduler.add_run_end_callback(status_printer.stop)
        scheduler.add_kill_signal_callback(status_printer.pause)

    # Add log manager hooks
    log_manager = LogManager(jobs)
    scheduler.add_job_status_change_callback(
        lambda spec, _old, new: log_manager.on_job_status_change(spec, new)
    )

    # Setup instrumentation
    inst = instrumentation.get()
    if inst is not None:
        inst.start()

        # Add instrumentation hooks
        scheduler.add_run_start_callback(inst.on_scheduler_start)
        scheduler.add_run_end_callback(inst.on_scheduler_end)
        scheduler.add_job_status_change_callback(
            lambda spec, _old, new: inst.on_job_status_change(spec, new)
        )

    # Run the scheduler and cleanup
    try:
        results = await scheduler.run()
    finally:
        await backend.close()

    # Finalize instrumentation
    if inst is not None:
        inst.stop()
        instrumentation.flush()

    return results
