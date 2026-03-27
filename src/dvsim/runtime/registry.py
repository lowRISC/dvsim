# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Registry of different runtime backends. Built-in backends are registered by default."""

from collections.abc import Callable
from typing import Any, NewType, TypeAlias

from dvsim.launcher.base import Launcher
from dvsim.launcher.fake import FakeLauncher
from dvsim.launcher.lsf import LsfLauncher
from dvsim.launcher.nc import NcLauncher
from dvsim.launcher.sge import SgeLauncher
from dvsim.launcher.slurm import SlurmLauncher
from dvsim.logging import log
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.legacy import LegacyLauncherAdapter
from dvsim.runtime.local import LocalRuntimeBackend

BackendType = NewType("BackendType", str)

BackendFactory: TypeAlias = Callable[..., RuntimeBackend]


class BackendRegistry:
    """Registry mapping backend names to factories/constructors of runtime backends."""

    def __init__(self) -> None:
        """Construct a new runtime backend registry."""
        self._registry: dict[BackendType, BackendFactory] = {}
        self._default: BackendType | None = None

    def register(
        self, name: BackendType, factory: BackendFactory, *, is_default: bool = False
    ) -> None:
        """Register a new runtime backend (factory/constructor) under a given name."""
        if name in self._registry:
            msg = f"Backend '{name}' is already registered"
            raise ValueError(msg)
        log.debug("New runtime backend registered: %s", name)
        self._registry[name] = factory
        if is_default:
            self.set_default(name)

    def set_default(self, name: BackendType) -> None:
        """Set the default runtime backend, which should be used unless specified otherwise."""
        log.debug("Configured default backend: %s", name)
        self._default = name

    def get_default(self) -> BackendType | None:
        """Get the configured default runtime backend type."""
        return self._default

    def get(self, name: BackendType | None = None) -> BackendFactory:
        """Retrieve a backend factory by its registered name."""
        name = self._default if name is None else name
        if name is None:
            raise ValueError("No default backend configured or backend name given")

        try:
            return self._registry[name]
        except KeyError as e:
            msg = f"Unknown backend '{name}'"
            raise KeyError(msg) from e

    def create(
        self, name: BackendType, *args: list[Any], **kwargs: dict[str, Any]
    ) -> RuntimeBackend:
        """Instantiate a runtime backend by its registered name."""
        factory = self.get(name)
        return factory(*args, **kwargs)

    def available(self) -> list[str]:
        """Return names of all registered backends."""
        return sorted(self._registry.keys())


# Default global registry
backend_registry = BackendRegistry()


def register_backend(name: BackendType, cls: type[RuntimeBackend]) -> None:
    """Register a standard runtime backend."""
    backend_registry.register(name, cls)


# Helper for registering runtime backends for legacy launchers.
# Can be removed when all legacy launchers are migrated.
def register_legacy_launcher_backend(name: BackendType, launcher_cls: type[Launcher]) -> None:
    """Register a legacy launcher class as a runtime backend by wrapping it in an adapter."""

    def factory(*args: list[Any], **kwargs: dict[str, Any]) -> RuntimeBackend:
        return LegacyLauncherAdapter(launcher_cls, *args, **kwargs)

    backend_registry.register(name, factory)


# Register built-in backends. TODO: migrate the legacy launchers to runtime backends.
register_backend(BackendType("local"), LocalRuntimeBackend)
register_legacy_launcher_backend(BackendType("fake"), FakeLauncher)
register_legacy_launcher_backend(BackendType("lsf"), LsfLauncher)
register_legacy_launcher_backend(BackendType("nc"), NcLauncher)
register_legacy_launcher_backend(BackendType("sge"), SgeLauncher)
register_legacy_launcher_backend(BackendType("slurm"), SlurmLauncher)


# TODO: Hack to support site-specific closed source custom launchers. These should be migrated to
# use the registry / a plugin system, and then the below should be dropped.
try:
    from edacloudlauncher.EdaCloudLauncher import (  # type: ignore[report-missing-imports]
        EdaCloudLauncher,
    )

    register_legacy_launcher_backend(BackendType("edacloud"), EdaCloudLauncher)
except ImportError:
    pass
