# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Registry of different runtime backends. Built-in backends are registered by default."""

import importlib
from collections.abc import Callable, Iterator, Mapping
from typing import Any, NewType, TypeAlias

from dvsim.launcher.base import Launcher
from dvsim.logging import log
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.legacy import LegacyLauncherAdapter

BackendType = NewType("BackendType", str)

BackendFactory: TypeAlias = Callable[..., RuntimeBackend]


class BackendRegistry(Mapping):
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
            self.default = name

    def create(
        self, name: BackendType | None, *args: list[Any], **kwargs: dict[str, Any]
    ) -> RuntimeBackend:
        """Instantiate a runtime backend by its registered name."""
        name = name if name is not None else self._default
        if name is None:
            raise RuntimeError("Cannot create a RuntimeBackend with no name or configured default")
        factory = self[name]
        return factory(*args, **kwargs)

    def clear(self) -> None:
        """Clear the backend registry."""
        log.debug("Cleared the backend registry.")
        self._registry.clear()
        self._default = None

    @property
    def default(self) -> BackendType | None:
        """Get the configured default runtime backend type."""
        return self._default

    @default.setter
    def default(self, name: BackendType) -> None:
        """Set the default runtime backend, which should be used unless specified otherwise."""
        log.debug("Configured default backend: %s", name)
        self._default = name

    def __getitem__(self, key: BackendType) -> BackendFactory:
        """Retrieve a backend factory by its registered name."""
        try:
            return self._registry[key]
        except KeyError as e:
            msg = f"Unknown backend '{key}'"
            raise KeyError(msg) from e

    def __iter__(self) -> Iterator[BackendType]:
        """Iterate over the registered backends."""
        return iter(self._registry)

    def __len__(self) -> int:
        """Get the number of registered backends."""
        return len(self._registry)


# Default global registry
backend_registry = BackendRegistry()


def register_backend(name: BackendType, backend_cls: type[RuntimeBackend] | str) -> None:
    """Register a standard runtime backend.

    Arguments:
        name: The name of the backend to register.
        backend_cls: Either the RuntimeBackend class, or a string to lazily import & load the
          RuntimeBackend from, where the string is like 'module.path.RuntimeBackendSubClass'.

    """
    if not isinstance(backend_cls, str):
        backend_registry.register(name, backend_cls)
        return
    if "." not in backend_cls:
        raise ValueError("Expected lazy import format like 'module.path.RuntimeBackendSubClass'")

    def lazy_factory(*args: list[Any], **kwargs: dict[str, Any]) -> RuntimeBackend:
        module_path, class_name = backend_cls.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        if not isinstance(cls, type) and issubclass(cls, RuntimeBackend):
            msg = f"Lazily registered backend '{cls}' is not a valid backend."
            raise TypeError(msg)
        return cls(*args, **kwargs)

    backend_registry.register(name, lazy_factory)


# Helper for registering runtime backends for legacy launchers.
# Can be removed when all legacy launchers are migrated.
def register_legacy_launcher_backend(name: BackendType, launcher_cls: type[Launcher] | str) -> None:
    """Register a legacy launcher class as a runtime backend by wrapping it in an adapter.

    Arguments:
        name: The name of the backend to register.
        launcher_cls: Either the Launcher class, or a string to lazily import & load the
          Launcher from, where the string is like 'module.path.LauncherSubClass'.

    """
    if not isinstance(launcher_cls, str):

        def launcher_factory(*args: list[Any], **kwargs: dict[str, Any]) -> RuntimeBackend:
            return LegacyLauncherAdapter(launcher_cls, *args, **kwargs)

        backend_registry.register(name, launcher_factory)
        return
    if "." not in launcher_cls:
        raise ValueError("Expected lazy import format like 'module.path.LauncherSubClass'")

    def lazy_factory(*args: list[Any], **kwargs: dict[str, Any]) -> RuntimeBackend:
        module_path, class_name = launcher_cls.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        if not isinstance(cls, type) or not issubclass(cls, Launcher):
            msg = f"Lazily registered launcher '{cls}' is not a valid launcher."
            raise TypeError(msg)
        return LegacyLauncherAdapter(cls, *args, **kwargs)

    backend_registry.register(name, lazy_factory)


# Register built-in backends. TODO: migrate the legacy launchers to runtime backends.
register_backend(BackendType("local"), "dvsim.runtime.local.LocalRuntimeBackend")
register_backend(BackendType("fake"), "dvsim.runtime.fake.FakeRuntimeBackend")
register_legacy_launcher_backend(BackendType("lsf"), "dvsim.launcher.lsf.LsfLauncher")
register_legacy_launcher_backend(BackendType("nc"), "dvsim.launcher.nc.NcLauncher")
register_legacy_launcher_backend(BackendType("sge"), "dvsim.launcher.sge.SgeLauncher")
register_legacy_launcher_backend(BackendType("slurm"), "dvsim.launcher.slurm.SlurmLauncher")

# TODO: Hack to support site-specific closed source custom launchers. These should be migrated to
# use the registry / a plugin system, and then the below should be dropped.
register_legacy_launcher_backend(
    BackendType("edacloud"), "edacloudlauncher.EdaCloudLauncher.EdaCloudLauncher"
)
