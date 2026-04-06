# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim Runtime Backends."""

import importlib
from collections.abc import Generator

import pytest
from hamcrest import (
    assert_that,
    calling,
    equal_to,
    instance_of,
    raises,
)
from pytest_mock import MockerFixture

from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.legacy import LegacyLauncherAdapter
from dvsim.runtime.local import LocalRuntimeBackend
from dvsim.runtime.registry import (
    BackendType,
    backend_registry,
    register_backend,
    register_legacy_launcher_backend,
)
from tests.test_scheduler import MockLauncher


@pytest.fixture(autouse=True)
def clear_registry() -> Generator[None, None, None]:
    """Automatically clear the backend registry between each test."""
    backend_registry.clear()
    yield
    backend_registry.clear()


class TestRegistry:
    """Unit tests for the runtime registry."""

    @staticmethod
    def test_register_backend() -> None:
        """Test that the regular RuntimeBackends can be registered."""
        assert_that(
            calling(backend_registry.create).with_args(BackendType("local")), raises(KeyError)
        )
        register_backend(BackendType("local"), LocalRuntimeBackend)
        backend = backend_registry.create(BackendType("local"))
        assert_that(backend, instance_of(RuntimeBackend))
        assert_that(backend.name, equal_to("local"))

    @staticmethod
    def test_lazy_register_backend(mocker: MockerFixture) -> None:
        """Test that the RuntimeBackends can be lazily registered via importlib."""
        # Mock (spy) on importlib.import_module to find out when it is called
        module_name = "dvsim.runtime.local"
        mock_import = mocker.spy(importlib, "import_module")

        # The module should only be imported after we actually create an instance.
        assert_that(
            calling(backend_registry.create).with_args(BackendType("local")), raises(KeyError)
        )
        assert_that(mock_import.call_count, equal_to(0))
        register_backend(BackendType("local"), f"{module_name}.LocalRuntimeBackend")
        assert_that(mock_import.call_count, equal_to(0))
        backend = backend_registry.create(BackendType("local"))
        assert_that(backend, instance_of(RuntimeBackend))
        assert_that(backend.name, equal_to("local"))
        assert_that(mock_import.call_count, equal_to(1))

    @staticmethod
    def test_register_launcher() -> None:
        """Test that the legacy Launchers can be registered."""
        assert_that(
            calling(backend_registry.create).with_args(BackendType("mock")), raises(KeyError)
        )
        register_legacy_launcher_backend(BackendType("mock"), MockLauncher)
        backend = backend_registry.create(BackendType("mock"))
        assert_that(backend, instance_of(LegacyLauncherAdapter))
        assert_that(backend.name, equal_to("mock"))

    @staticmethod
    def test_lazy_register_launcher(mocker: MockerFixture) -> None:
        """Test that the legacy Launchers can be lazily registered via importlib."""
        # Mock (spy) on importlib.import_module to find out when it is called
        module_name = "tests.test_scheduler"
        mock_import = mocker.spy(importlib, "import_module")

        # The module should only be imported after we actually create an instance.
        assert_that(
            calling(backend_registry.create).with_args(BackendType("mock")), raises(KeyError)
        )
        assert_that(mock_import.call_count, equal_to(0))
        register_legacy_launcher_backend(BackendType("mock"), f"{module_name}.MockLauncher")
        assert_that(mock_import.call_count, equal_to(0))
        backend = backend_registry.create(BackendType("mock"))
        assert_that(backend, instance_of(LegacyLauncherAdapter))
        assert_that(backend.name, equal_to("mock"))
        assert_that(mock_import.call_count, equal_to(1))
