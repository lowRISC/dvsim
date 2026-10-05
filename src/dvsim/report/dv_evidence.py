# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Regression results in the tool-neutral `lowrisc-dv-evidence` format.

These models are the format's definition, and `doc/dv_evidence.md` describes them. It lives here
because dvsim is what produces the file, so anything reading one can be written against a public
spec rather than against whichever consumer happened to be built first.

The format carries no planning-tool concepts, so a verification plan can be scored from any
regression flow that emits it, and a person can write one by hand.

Built from what the scheduler concludes about each job, through its completion hook. That is the
same state the JSON report is derived from, so the two cannot disagree about a run, and it is
available early enough for the vPlan job to read while the run is still going.

Each run is appended to a log in the scratch directory as it finishes rather than accumulated in
memory, so the scratch directory is the only thing standing between the runs and the job that
scores them.
"""

import json
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dvsim.job.data import JobSpec, JobStatusInfo
from dvsim.job.status import JobStatus
from dvsim.logging import log
from dvsim.report.data import IPMeta
from dvsim.scheduler.core import ALL_FAILED_DEP, FAILED_DEP, KILLED_QUEUED, KILLED_SCHEDULED

__all__ = (
    "EvidenceFile",
    "Outcome",
    "RunEvidenceLog",
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

    There is no waived outcome. A waiver needs an owner and a date, and a regression can supply
    neither, so the format only allows one on an inspection, which is written by hand.
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

    dvsim only ever fills the `testcase` half. The format also has an `inspection` key, for claims
    no simulation can measure, and those records are written by hand.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    testcase: dict[str, list[TestRun]]

    schema_id: str = Field(default=SCHEMA_ID, alias="schema")
    dut: str | None = None
    tool: str | None = None
    produced_by: str | None = None
    revision: str | None = None
    timestamp: str | None = None


class RunEvidenceLog:
    """Append-only record of how each test run ended, in one sim cfg's scratch directory.

    Fed by `Scheduler.add_job_completion_callback`, so a job cancelled before it ever started is
    recorded too, and a test the plan expected reads as a hole rather than as an absent test.

    Each run is appended as it finishes rather than held in memory until the end, so the log on
    disk, not a live dvsim process, is what the vPlan job reads. That is what lets the vPlan step
    be retried, or a part-finished run be picked up, without the earlier outcomes having been
    lost with the process that saw them.

    One JSON object per line, opened and closed per run, so a dvsim that is killed still leaves a
    readable log of everything that had finished by then. Appending costs one short write per
    test, against a simulation that took minutes.
    """

    def __init__(self, path: Path) -> None:
        """Log to `path`, which is created on the first write."""
        self.path = path

    def start(self) -> None:
        """Begin an empty log, discarding whatever an earlier run left in the same scratch area.

        A scratch path is reused between invocations on one branch, so without this a second run
        would score the vPlan from both. Resuming a part-finished run is the case that would want
        the opposite, and it would skip this rather than change what `record` writes.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def record(self, spec: JobSpec, status: JobStatus, reason: JobStatusInfo | None) -> None:
        """Append how one job ended, keeping only the ones that run a test.

        Written under the job name, which is the name a vPlan addresses. Reseeds of one test share
        it and are told apart by their seeds.
        """
        if spec.target != RUN_TARGET:
            return
        failed = status != JobStatus.PASSED
        run = TestRun(
            status=run_outcome(status, reason),
            seed=spec.seed,
            log=spec.log_path,
            message=reason.message if reason is not None and failed else None,
            line=_first_line(reason) if failed else None,
        )
        record = {"test": spec.name, **run.model_dump(mode="json", exclude_none=True)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def runs(self) -> dict[str, list[TestRun]]:
        """Read the log back, grouped by test name, in the order the runs finished.

        A line that will not parse is dropped with a warning rather than failing the job: dvsim
        can be killed mid-write, and one torn line is not a reason to score nothing.
        """
        runs: dict[str, list[TestRun]] = {}
        if not self.path.is_file():
            log.warning(
                "No run log at '%s', so the vPlan is scored from no test results.", self.path
            )
            return runs
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                name = record.pop("test")
                runs.setdefault(name, []).append(TestRun.model_validate(record))
            except (ValueError, KeyError, ValidationError):
                log.warning("Skipping an unreadable line in the run log '%s'.", self.path)
        return runs

    def evidence(
        self,
        *,
        block: IPMeta,
        tool: str | None = None,
        timestamp: str | None = None,
    ) -> EvidenceFile:
        """Build the evidence document from everything the log holds."""
        return EvidenceFile(
            testcase=self.runs(),
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
