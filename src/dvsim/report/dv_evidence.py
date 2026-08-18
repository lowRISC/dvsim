# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Regression results in the tool-neutral `lowrisc-dv-evidence` format.

dvplan defines the format, so a vPlan can be back-annotated from any regression flow and a person
can write one by hand. What dvsim writes here is a plain serialisation of what it already knows.

Built from what the scheduler concludes about each job, through its completion hook. That is the
same state the JSON report is derived from, so the two cannot disagree about a run, and it is
available early enough for the vPlan job to read while the run is still going.
"""

from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.report.data import IPMeta
from dvsim.scheduler.core import ALL_FAILED_DEP, FAILED_DEP, KILLED_QUEUED, KILLED_SCHEDULED

__all__ = (
    "EvidenceFile",
    "Outcome",
    "RunEvidenceCollector",
    "run_outcome",
    "write_evidence",
)

# What the file calls itself. Named for the evidence it holds, which is test runs and manual
# inspections alike, rather than for either metric type
SCHEMA_ID = "lowrisc-dv-evidence"

# The `target` the scheduler gives a job that runs a test. Builds and coverage jobs share the
# same result stream and are filtered out on this
RUN_TARGET = "run"

# Reasons the scheduler reports for a job it cancelled rather than ran, imported rather than
# restated so a reworded message cannot silently stop matching
_CANCELLED_REASONS = frozenset(
    reason.message for reason in (FAILED_DEP, ALL_FAILED_DEP, KILLED_SCHEDULED, KILLED_QUEUED)
)


class Outcome(Enum):
    """How one run of a test ended, in the neutral format's vocabulary.

    There is no waived outcome: dvplan requires an owner and a date on a waiver, and a regression
    can supply neither. A known failure is accepted there by recording an inspection instead.
    """

    PASSED = "passed"
    FAILED = "failed"
    KILLED = "killed"
    NOT_RUN = "not_run"

    def __str__(self) -> str:
        """Return the outcome as it appears in a results file."""
        return self.value


def run_outcome(status: JobStatus, reason: JobStatusInfo | None) -> Outcome:
    """Map a job's terminal status onto the neutral format's vocabulary.

    `JobStatus.KILLED` covers both a job terminated while executing and one cancelled before it was
    dispatched, which are different answers to "did this test run at all". The reason separates
    them, and the scheduler records one against every job it completes.
    """
    if status == JobStatus.PASSED:
        return Outcome.PASSED
    if status == JobStatus.FAILED:
        return Outcome.FAILED
    if reason is not None and reason.message in _CANCELLED_REASONS:
        return Outcome.NOT_RUN
    return Outcome.KILLED


class TestRun(BaseModel):
    """One run of one test."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False  # Named Test*, so pytest would otherwise collect it as a test class.

    status: Outcome
    seed: int | None = None
    log: Path | None = None
    message: str | None = None
    line: int | None = None


class EvidenceFile(BaseModel):
    """A regression's results, in the tool-neutral evidence format.

    dvsim only ever fills the `testcase` half. The format also carries manual inspections, which a
    person writes by hand.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    testcase: dict[str, list[TestRun]]

    schema_id: str = Field(default=SCHEMA_ID, alias="schema")
    dut: str | None = None
    tool: str | None = None
    produced_by: str | None = None
    revision: str | None = None
    timestamp: str | None = None


class RunEvidenceCollector:
    """Accumulates the outcome of every test run of one flow, as the scheduler concludes them.

    Fed by `Scheduler.add_job_completion_callback`, so a job cancelled before it ever started is
    recorded too, and a test the plan expected reads as a hole rather than as an absent test.
    """

    def __init__(self) -> None:
        """Start with nothing recorded. Runs arrive as the scheduler completes them."""
        self._runs: dict[str, list[TestRun]] = {}

    def record(self, spec: JobSpec, status: JobStatus, reason: JobStatusInfo | None) -> None:
        """Record how one job ended, keeping only the ones that run a test.

        Grouped by job name, which is the name a vPlan addresses. Reseeds of one test share it and
        are told apart by their seeds.
        """
        if spec.target != RUN_TARGET:
            return
        failed = status != JobStatus.PASSED
        self._runs.setdefault(spec.name, []).append(
            TestRun(
                status=run_outcome(status, reason),
                seed=spec.seed,
                log=spec.log_path,
                message=reason.message if reason is not None and failed else None,
                line=_first_line(reason) if failed else None,
            )
        )

    def evidence(
        self,
        *,
        block: IPMeta,
        tool: str | None = None,
        timestamp: str | None = None,
    ) -> EvidenceFile:
        """Build the evidence document for everything recorded so far."""
        return EvidenceFile(
            testcase=self._runs,
            dut=block.variant_name(sep="/"),
            tool=tool,
            produced_by=_produced_by(),
            revision=_revision(block),
            timestamp=timestamp,
        )


def write_evidence(path: Path, evidence: EvidenceFile) -> Path:
    """Write the evidence file, creating its directory if needed, and return its path.

    `IPMeta.url` is already stripped of credentials by `git_origin_url`, which matters because this
    file is archived alongside the reports.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        evidence.model_dump_json(by_alias=True, indent=2, exclude_none=True), encoding="utf-8"
    )
    log.debug("Wrote results for %d tests to '%s'", len(evidence.testcase), path)
    return path


def _revision(block: IPMeta) -> str:
    """Describe the revision the results were produced against, marking an uncommitted tree.

    Marked the way `sim.report` marks it, since the two describe the same run. This file outlives
    the run, so it is the only chance to record it.
    """
    revision = block.revision_info or block.url or block.commit
    if block.dirty and "(dirty)" not in revision:
        revision += " (dirty)"
    return revision


def _produced_by() -> str:
    """Name dvsim and its version, or just dvsim when it is not installed as a package."""
    try:
        return f"dvsim {version('dvsim').strip()}"
    except PackageNotFoundError:
        log.debug("DVSim package not found, so its version is left out of the results")
        return "dvsim"


def _first_line(reason: JobStatusInfo | None) -> int | None:
    """Get the first log line a failure was reported at, where one was recorded."""
    if reason is None or not reason.lines:
        return None
    first = reason.lines[0]
    return first if isinstance(first, int) else first[0]
