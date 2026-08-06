# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test the DVSim Runtime Backends."""

import asyncio
import importlib
import io
import shlex
import sys
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from hamcrest import (
    assert_that,
    calling,
    contains_string,
    equal_to,
    instance_of,
    raises,
)
from pytest_mock import MockerFixture

from dvsim.job.status import JobStatus
from dvsim.runtime import local as local_module
from dvsim.runtime.backend import RuntimeBackend
from dvsim.runtime.data import JobCompletionEvent
from dvsim.runtime.legacy import LegacyLauncherAdapter
from dvsim.runtime.local import LocalRuntimeBackend
from dvsim.runtime.registry import (
    BackendType,
    backend_registry,
    register_backend,
    register_legacy_launcher_backend,
)
from tests.test_scheduler import MockLauncher, job_spec_factory


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


async def _run_job_to_completion(
    backend: LocalRuntimeBackend, job: object, timeout: float = 20.0
) -> list[JobCompletionEvent]:
    """Submit a single job to a backend and wait for its completion event(s)."""
    events: list[JobCompletionEvent] = []
    done = asyncio.Event()

    async def on_complete(batch: object) -> None:
        events.extend(batch)
        done.set()

    backend.attach_completion_callback(on_complete)
    await backend.submit(job)
    await asyncio.wait_for(done.wait(), timeout=timeout)
    return events


def _python_cmd(program: str) -> str:
    """Build a shell command that runs `program` with the current test interpreter."""
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(program)}"


class TestLocalBackendStreaming:
    """Tests for `LocalRuntimeBackend` streaming subprocess output into the job log."""

    @staticmethod
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_streams_output_to_log(tmp_path: Path) -> None:
        """A normal job's stdout is written to its log file and the job passes.

        The sentinel is emitted via `chr()` codes so the literal string never appears in the
        command line: `_monitor_job` writes the command into the log as an "[Executing]" preamble,
        so asserting on a literal that is also in the command would pass even if no subprocess
        output were captured at all.
        """
        sentinel = "STREAMED_OUTPUT_OK"
        program = f"print(''.join(chr(c) for c in {[ord(c) for c in sentinel]}))"
        job = job_spec_factory(tmp_path, cmd=_python_cmd(program))
        backend = LocalRuntimeBackend()

        events = await _run_job_to_completion(backend, job)

        assert_that(len(events), equal_to(1))
        assert_that(events[0].status, equal_to(JobStatus.PASSED))
        assert_that(job.log_path.read_text(), contains_string(sentinel))

    @staticmethod
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_long_line_does_not_deadlock(tmp_path: Path) -> None:
        """A single line far larger than the 64 KiB StreamReader limit is logged, not deadlocked.

        Regression test for the original bug: `readline()` raised `LimitOverrunError` on such a
        line, killing the reader task; with nobody draining the pipe the subprocess blocked
        writing and `process.wait()` hung forever. The `@timeout` turns a re-regression into a
        test failure rather than a hang.
        """
        fill = "x"
        line_len = 512 * 1024  # 512 KiB on a single line, no embedded newline
        program = f"import sys; sys.stdout.write('{fill}' * {line_len})"
        job = job_spec_factory(tmp_path, cmd=_python_cmd(program))
        backend = LocalRuntimeBackend()

        events = await _run_job_to_completion(backend, job)

        assert_that(events[0].status, equal_to(JobStatus.PASSED))
        # The entire unbroken run must reach the log intact (the "[Executing]" preamble contains
        # only a single `x`, so a run this long can only be the job's own output).
        assert_that(job.log_path.read_text(), contains_string(fill * line_len))

    @staticmethod
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_decodes_multibyte_across_chunk_boundary() -> None:
        """A multibyte UTF-8 character split across two chunk reads is decoded correctly.

        `_log_from_pipe` reads fixed-size chunks, so a character whose bytes straddle a chunk
        boundary must be held by the incremental decoder rather than corrupted.
        """
        chunk = LocalRuntimeBackend.SUBPROCESS_READ_CHUNK_SIZE
        # Place the two bytes of 'é' (U+00E9 -> 0xC3 0xA9) either side of the first chunk boundary.
        data = b"a" * (chunk - 1) + "é".encode() + b"b" * 10
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()

        log_file = io.StringIO()
        handle = SimpleNamespace(log_file=log_file, spec=SimpleNamespace(full_name="job"))

        await LocalRuntimeBackend()._log_from_pipe(handle, reader)  # noqa: SLF001

        expected = "a" * (chunk - 1) + "é" + "b" * 10
        assert_that(log_file.getvalue(), equal_to(expected))

    @staticmethod
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_reader_error_is_logged_not_raised(mocker: MockerFixture) -> None:
        """An unexpected error while writing the log is caught and logged, not propagated.

        A dead reader task stops draining the pipe and re-introduces the deadlock, so
        `_log_from_pipe` must never let an unexpected exception escape - but it must also make the
        failure visible via `log.exception` rather than swallow it silently.
        """
        spy = mocker.spy(local_module.log, "exception")

        class _RaisingLog:
            def write(self, _: str) -> int:
                raise OSError("simulated disk-full")

            def flush(self) -> None:
                pass

        reader = asyncio.StreamReader()
        reader.feed_data(b"some output\n")
        reader.feed_eof()
        handle = SimpleNamespace(log_file=_RaisingLog(), spec=SimpleNamespace(full_name="job"))

        # Must return normally (no exception bubbling out to kill the caller's task)...
        await LocalRuntimeBackend()._log_from_pipe(handle, reader)  # noqa: SLF001

        # ...but must surface the failure via `log.exception` rather than swallow it silently.
        assert_that(spy.call_count, equal_to(1))

    @staticmethod
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_cancellation_is_silent(mocker: MockerFixture) -> None:
        """Cancelling the reader (the normal teardown path) is not reported as an error."""
        spy = mocker.spy(local_module.log, "exception")

        reader = asyncio.StreamReader()  # never fed EOF: the read blocks until cancelled
        log_file = io.StringIO()
        handle = SimpleNamespace(log_file=log_file, spec=SimpleNamespace(full_name="job"))

        task = asyncio.create_task(
            LocalRuntimeBackend()._log_from_pipe(handle, reader)  # noqa: SLF001
        )
        # Let the task start and block on the first read before cancelling it.
        for _ in range(3):
            await asyncio.sleep(0)
        task.cancel()
        await task  # `CancelledError` is caught internally, so this returns without raising.

        assert_that(spy.call_count, equal_to(0))
