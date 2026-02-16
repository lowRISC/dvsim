# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler instrumentation for system resource usage."""

import os
import threading
import time
from dataclasses import dataclass
from typing import TypeAlias

import psutil

from dvsim.instrumentation.base import (
    InstrumentationFragments,
    JobFragment,
    SchedulerFragment,
    SchedulerInstrumentation,
)
from dvsim.job.data import JobSpec
from dvsim.job.status import JobStatus

__all__ = (
    "ResourceInstrumentation",
    "ResourceJobFragment",
    "ResourceSchedulerFragment",
)


@dataclass
class ResourceSchedulerFragment(SchedulerFragment):
    """Instrumented metrics about the scheduler reported by the `ResourceInstrumentation`."""

    # Scheduler / DVSim process overhead
    scheduler_rss_bytes: int | None = None
    scheduler_vms_bytes: int | None = None
    scheduler_cpu_percent: float | None = None
    scheduler_cpu_time: float | None = None

    # System-wide metrics
    sys_rss_bytes: int | None = None
    sys_swap_used_bytes: int | None = None
    sys_cpu_percent: float | None = None
    sys_cpu_per_core: list[float] | None = None

    num_resource_samples: int = 0


@dataclass
class ResourceJobFragment(JobFragment):
    """Instrumented metrics about jobs reported by the `ResourceInstrumentation`.

    Since we can't directly measure each deployed job, these are instead averages and system
    information over the course of the job's runtime.
    """

    max_rss_bytes: int | None = None
    avg_rss_bytes: float | None = None
    avg_cpu_percent: float | None = None
    avg_cpu_per_core: list[float] | None = None

    num_resource_samples: int = 0


class JobResourceAggregate:
    """Resource Instrumentation aggregation for a single deployed job.

    Tracks aggregate information over a number of samples whilst minimizing memory usage.
    """

    def __init__(self, job: JobSpec, num_cores: int | None) -> None:
        """Construct an aggregate for storing sampling info for a given job specification.

        Arguments:
            job: The specification of the job which is having its information aggregated.
            num_cores: The number of logical CPU cores available on the host system.

        """
        self.job_spec = job
        self.num_cores = num_cores
        self.sample_count = 0
        self.sum_rss = 0.0
        self.max_rss = 0
        self.sum_cpu = 0.0
        if num_cores:
            self.sum_cpu_per_core = [0.0] * num_cores

    def add_sample(self, rss: int, cpu: float, cpu_per_core: list[float]) -> None:
        """Aggregate an additional resource sample taken during this job's active window."""
        self.sample_count += 1
        self.sum_rss += rss
        self.max_rss = max(self.max_rss, rss)
        self.sum_cpu += cpu
        if self.num_cores:
            self.sum_cpu_per_core = [
                total + n for total, n in zip(self.sum_cpu_per_core, cpu_per_core, strict=True)
            ]

    def finalize(self) -> ResourceJobFragment:
        """Finalize the aggregated information for a job, generating a report fragment."""
        if self.sample_count == 0:
            return ResourceJobFragment(self.job_spec)

        if self.num_cores:
            avg_cpu_per_core = [x / self.sample_count for x in self.sum_cpu_per_core]
        else:
            avg_cpu_per_core = None

        return ResourceJobFragment(
            self.job_spec,
            max_rss_bytes=self.max_rss,
            avg_rss_bytes=self.sum_rss / self.sample_count,
            avg_cpu_percent=self.sum_cpu / self.sample_count,
            avg_cpu_per_core=avg_cpu_per_core,
            num_resource_samples=self.sample_count,
        )


# Unique identifier to disambiguate a job (full_name, target)
JobId: TypeAlias = tuple[str, str]


class ResourceInstrumentation(SchedulerInstrumentation):
    """Resource instrumentation for the scheduler.

    Collects information about the compute resources used throughout the entire duration of
    the scheduler, as well as during the window within which each job is dispatched. This
    includes memory usage (max & avg RSS bytes), virtual memory (VMS bytes), swap usage, CPU
    time and per-core CPU utilisation.

    Since we have no access to job sub-processes, per-job instrumentation is the aggregate
    of the samples that fall within that job's execution window.
    """

    def __init__(self, sample_interval: float = 0.5) -> None:
        """Construct a resource instrumentation.

        Arguments:
            sample_interval: The period (in seconds) per poll / sample produced.

        """
        self.sample_interval = sample_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._scheduler_process = psutil.Process(os.getpid())
        self._num_cores = psutil.cpu_count(logical=True)
        self._sample_count = 0

        # Scheduler (DVSim process) / System Memory usage
        self._scheduler_sum_rss = 0
        self._scheduler_max_rss = 0
        self._scheduler_sum_vms = 0
        self._sys_max_rss = 0
        self._sys_max_swap = 0

        # Scheduler (DVSim process) / System CPU usage
        self._scheduler_cpu_time_start = 0
        self._scheduler_cpu_time_end = 0
        self._scheduler_sum_cpu = 0
        self._sys_sum_cpu = 0
        if self._num_cores is not None:
            self._sys_sum_cpu_per_core = [0] * self._num_cores

        # Job aggregate metrics
        self._running_jobs: dict[JobId, JobResourceAggregate] = {}
        self._finished_jobs: dict[JobId, JobResourceAggregate] = {}

    def _scheduler_cpu_time(self) -> float | int:
        """Get the CPU time of the scheduler process.

        Includes user mode time an system time (kernel mode). Excludes the user & system time
        of child processes and any iowait time spent for blocking I/O to complete.
        """
        return sum(self._scheduler_process.cpu_times()[:2])

    def _start(self) -> None:
        """Start system-wide sampling in the background on another thread."""
        self._running = True
        self._scheduler_process.cpu_percent(None)  # Start measuring
        self._thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._thread.start()

    def _stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join()

    def _sampling_loop(self) -> None:
        next_run_at = time.time()
        while self._running:
            next_run_at += self.sample_interval

            scheduler_memory_info = self._scheduler_process.memory_info()
            sys_rss = psutil.virtual_memory().used
            sys_cpu = psutil.cpu_percent(None)
            sys_cpu_per_core = psutil.cpu_percent(percpu=True)

            # Update scheduler aggregates
            self._sample_count += 1
            self._scheduler_sum_rss += scheduler_memory_info.rss
            self._scheduler_sum_vms += scheduler_memory_info.vms
            self._scheduler_sum_cpu += self._scheduler_process.cpu_percent(None)
            self._scheduler_max_rss = max(self._scheduler_max_rss, scheduler_memory_info.rss)

            # Update system-wide metrics
            self._sys_max_swap = max(self._sys_max_swap, psutil.swap_memory().used)
            self._sys_max_rss = max(self._sys_max_rss, sys_rss)
            self._sys_sum_cpu += sys_cpu
            if self._num_cores is not None:
                self._sys_sum_cpu_per_core = [
                    total + n
                    for total, n in zip(self._sys_sum_cpu_per_core, sys_cpu_per_core, strict=True)
                ]

            # Update all running job aggregates with system sample
            with self._lock:
                for aggregate in self._running_jobs.values():
                    aggregate.add_sample(sys_rss, sys_cpu, sys_cpu_per_core)

            sleep_time = max(next_run_at - time.time(), 0)
            time.sleep(sleep_time)

    def on_scheduler_start(self) -> None:
        """Notify instrumentation that the scheduler has begun."""
        self._scheduler_cpu_time_start = self._scheduler_cpu_time()

    def on_scheduler_end(self) -> None:
        """Notify instrumentation that the scheduler has finished."""
        self._scheduler_cpu_time_end = self._scheduler_cpu_time()

    def on_job_status_change(self, job: JobSpec, status: JobStatus) -> None:
        """Notify instrumentation of a change in status for some scheduled job."""
        job_id = (job.full_name, job.target)

        with self._lock:
            running = job_id in self._running_jobs
            started = running or job_id in self._finished_jobs
            if not started and status != JobStatus.QUEUED:
                self._running_jobs[job_id] = JobResourceAggregate(job, self._num_cores)
                running = True
            if running and status.ended:
                aggregates = self._running_jobs.pop(job_id)
                self._finished_jobs[job_id] = aggregates

    def build_report_fragments(self) -> InstrumentationFragments | None:
        """Build report fragments from the collected instrumentation information."""
        if self._running:
            raise RuntimeError("Cannot build instrumentation report whilst still running!")

        if self._sample_count <= 0:
            scheduler_frag = ResourceSchedulerFragment()
        else:
            scheduler_cpu_time = self._scheduler_cpu_time_end - self._scheduler_cpu_time_start
            if self._num_cores is not None:
                sys_cpu_per_core = [s / self._sample_count for s in self._sys_sum_cpu_per_core]
            else:
                sys_cpu_per_core = None
            try:
                vms_bytes = round(self._scheduler_sum_vms / self._sample_count)
            except (ValueError, TypeError):
                # Suppress unknown types in VMS measurements
                vms_bytes = None

            scheduler_frag = ResourceSchedulerFragment(
                scheduler_rss_bytes=self._scheduler_max_rss,
                scheduler_vms_bytes=vms_bytes,
                scheduler_cpu_percent=self._scheduler_sum_cpu / self._sample_count,
                scheduler_cpu_time=scheduler_cpu_time,
                sys_rss_bytes=self._sys_max_rss,
                sys_cpu_percent=self._sys_sum_cpu / self._sample_count,
                sys_cpu_per_core=sys_cpu_per_core,
                sys_swap_used_bytes=self._sys_max_swap,
                num_resource_samples=self._sample_count,
            )

        aggregates = list(self._finished_jobs.values()) + list(self._running_jobs.values())
        job_frags = [aggregate.finalize() for aggregate in aggregates]
        return ([scheduler_frag], job_frags)
