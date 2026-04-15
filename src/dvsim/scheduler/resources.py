# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim scheduler resource (parallelism limitation) management."""

from collections import defaultdict
from collections.abc import Iterable
from enum import Enum
from typing import Protocol

from dvsim.job.data import JobSpec, ResourceMapping
from dvsim.logging import log

__all__ = (
    "ResourceManager",
    "ResourceProvider",
    "StaticResourceProvider",
)


class ResourceProvider(Protocol):
    """An abstraction of something that provides resource availability info to the scheduler."""

    is_dynamic: bool
    """Whether the resources returned by the provider can change over time."""

    async def get_capacity(self) -> ResourceMapping:
        """Get the capacity of resources available from this provider.

        An integer capacity defines a strict limit for parallelism of that resource, whereas `None`
        indicates no upper bound on parallelism.
        """
        ...


class StaticResourceProvider:
    """Provides information about static (unchanging) resource availability."""

    is_dynamic = False

    def __init__(self, limits: ResourceMapping) -> None:
        """Construct a ResourceProvider with defined static limits."""
        self._limits = limits

    async def get_capacity(self) -> ResourceMapping:
        """Get the static capacity of the resources available from this provider.

        An integer capacity defines a strict limit for parallelism of that resource, whereas `None`
        indicates no upper bound on parallelism.
        """
        return self._limits


class UnknownResourcePolicy(str, Enum):
    """Behaviour upon a job requesting a resource without any defined limit."""

    IGNORE = "ignore"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class ResourceManager:
    """Manages scheduler resources, limiting parallelism on a per-resource basis."""

    def __init__(
        self,
        provider: ResourceProvider,
        missing_policy: UnknownResourcePolicy = UnknownResourcePolicy.IGNORE,
    ) -> None:
        """Construct a ResourceManager instance."""
        self._provider = provider
        self._missing_policy = missing_policy
        self._usage = defaultdict(int)

    async def can_allocate(self, request: ResourceMapping) -> bool:
        """Check if a given resource request can be allocated, given current usage and limits."""
        capacity = await self._provider.get_capacity()
        for resource, needed in request.items():
            limit = capacity.get(resource)
            if limit is None:
                continue
            if needed is None or self._usage[resource] + needed > limit:
                return False
        return True

    async def try_allocate(self, request: ResourceMapping) -> bool:
        """Attempt to allocate the requested resources, recording their usage.

        Returns:
            True if successfully allocated, false otherwise.

        """
        # Note: we use no lock here on in `ResourceManager.release()` because we assume the
        # invariant that there is never an await between the check and the mutation. If the
        # code is changed in this manner, then both of these methods should acquire an
        # asyncio.Lock() first around their operation.
        if not await self.can_allocate(request):
            return False
        for resource, amount in request.items():
            if amount is not None:
                self._usage[resource] += amount
        return True

    def release(self, request: ResourceMapping) -> None:
        """Release a set of allocated resources."""
        for resource, amount in request.items():
            if amount is not None:
                self._usage[resource] -= amount

    def _log_usage(self, capacity: ResourceMapping, used: ResourceMapping) -> None:
        """Debug log individual job resource usage aggregates."""
        if log.isEnabledFor(log.DEBUG):
            for resource, usage in used.items():
                limit = capacity.get(resource)
                usage_str = str(usage) if usage is not None else "unlimited"
                limit_str = str(limit) if limit is not None else "unlimited"
                log.debug(
                    "Total '%s' resources used: %s,  limit: %s", resource, usage_str, limit_str
                )

    def _handle_missing_resource(self, job: JobSpec, resource: str, errors: list[str]) -> None:
        """Handle a job using an undefined resource, according to the configured policy.

        Args:
            job: the job with a missing resource
            resource: the name of the missing resource
            errors: the list of errors to append an error to if needed.

        """
        if not job.resources:
            return

        needed = job.resources.get(resource)
        message = f"Job '{job.full_name}' uses unknown resource '{resource}' ({needed} requested)"
        match self._missing_policy:
            case UnknownResourcePolicy.WARN:
                log.warning(message)
            case UnknownResourcePolicy.ERROR:
                log.error(message)
            case UnknownResourcePolicy.FATAL:
                errors.append(message)

    def _emit_validation_errors(
        self, missing_resources: list[str], limit_exceeded: list[str]
    ) -> None:
        """Emit aggregated job validation error messages according to the manager's configuration.

        Args:
            missing_resources: error messages for any resources used that were not defined.
            limit_exceeded: error messages for any job whose resources exceeded the defined limits.

        """
        if missing_resources:
            msg = "Job resources had errors:\n" + "\n".join(missing_resources + limit_exceeded)
            raise ValueError(msg)
        if limit_exceeded:
            msg = "Invalid job resource requirements:\n" + "\n".join(limit_exceeded)
            # If we know the available resources are static, this should be a fatal error.
            if not self._provider.is_dynamic:
                raise ValueError(msg)
            log.warning("%s", msg)

    async def validate_jobs(self, jobs: Iterable[JobSpec]) -> None:
        """Validate given jobs against known (initial) resource limits.

        Validate that the resources required by a list of jobs are less than those that are
        initially available from some resource providers. Note that if resources are not static,
        this is not a guarantee that resources will remain available.
        """
        capacity = await self._provider.get_capacity()
        aggregate: ResourceMapping = defaultdict(int)
        # Collect all errors before reporting to give more detailed info
        missing_resource_errors: list[str] = []
        limit_exceeded_errors: list[str] = []

        for job in jobs:
            if not job.resources:
                continue

            for resource, needed in job.resources.items():
                used = aggregate[resource]
                if needed is None:
                    aggregate[resource] = None
                elif used is not None:
                    aggregate[resource] = used + needed

                if resource not in capacity:
                    self._handle_missing_resource(job, resource, missing_resource_errors)
                    continue

                limit = capacity[resource]
                if limit is not None and (needed is None or needed > limit):
                    amount = "unlimited" if needed is None else f"{needed} of"
                    msg = (
                        f"Job '{job.full_name}' requires {amount} '{resource}' "
                        f"but the max available is {limit}"
                    )
                    limit_exceeded_errors.append(msg)

        self._log_usage(capacity, aggregate)
        self._emit_validation_errors(missing_resource_errors, limit_exceeded_errors)
