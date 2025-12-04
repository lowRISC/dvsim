# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Class describing simulation results."""

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from dvsim.testplan import Result

if TYPE_CHECKING:
    from dvsim.job.data import CompletedJobStatus

__all__ = ()

_REGEX_REMOVE = [
    # Remove UVM time.
    re.compile(r"@\s+[\d.]+\s+[np]s: "),
    re.compile(r"\[[\d.]+\s+[np]s\] "),
    # Remove assertion time.
    re.compile(r"\(time [\d.]+ [PF]S\) "),
    # Remove leading spaces.
    re.compile(r"^\s+"),
    # Remove extra white spaces.
    re.compile(r"\s+(?=\s)"),
]

_REGEX_STRIP = [
    # Strip TB instance name.
    re.compile(r"[\w_]*top\.\S+\.(\w+)"),
    # Strip assertion.
    re.compile(r"(?<=Assertion )\S+\.(\w+)"),
]

# Regular expression for a separator: EOL or some of punctuation marks.
_SEPARATOR_RE = "($|[ ,.:;])"

_REGEX_STAR = [
    # Replace hex numbers with 0x (needs to be called before other numbers).
    re.compile(r"0x\s*[\da-fA-F]+"),
    # Replace hex numbers with 'h (needs to be called before other numbers).
    re.compile(r"\'h\s*[\da-fA-F]+"),
    # Floating point numbers at the beginning of a word, example "10.1ns".
    # (needs to be called before other numbers).
    re.compile(r"(?<=[^a-zA-Z0-9])\d+\.\d+"),
    # Replace all isolated numbers. Isolated numbers are numbers surrounded by
    # special symbols, for example ':' or '+' or '_', excluding parenthesis.
    # So a number with a letter or a round bracket on any one side, is
    # considered non-isolated number and is not starred by these expressions.
    re.compile(r"(?<=[^a-zA-Z0-9\(\)])\d+(?=($|[^a-zA-Z0-9\(\)]))"),
    # Replace numbers surrounded by parenthesis after a space and followed by a
    # separator.
    re.compile(rf"(?<= \()\s*\d+\s*(?=\){_SEPARATOR_RE})"),
    # Replace hex/decimal numbers after an equal sign or a semicolon and
    # followed by a separator. Uses look-behind pattern which need a
    # fixed width, thus the apparent redundancy.
    re.compile(rf"(?<=[\w\]][=:])[\da-fA-F]+(?={_SEPARATOR_RE})"),
    re.compile(rf"(?<=[\w\]][=:] )[\da-fA-F]+(?={_SEPARATOR_RE})"),
    re.compile(rf"(?<=[\w\]] [=:])[\da-fA-F]+(?={_SEPARATOR_RE})"),
    re.compile(rf"(?<=[\w\]] [=:] )[\da-fA-F]+(?={_SEPARATOR_RE})"),
    # Replace decimal number at the beginning of the word.
    re.compile(r"(?<= )\d+(?=\S)"),
    # Remove decimal number at end of the word and before '=' or '[' or
    # ',' or '.' or '('.
    re.compile(r"(?<=\S)\d+(?=($|[ =\[,\.\(]))"),
    # Replace the instance string.
    re.compile(r"(?<=instance)\s*=\s*\S+"),
]


def _bucketize(fail_msg: str) -> str:
    """Generalise error messages to create common error buckets."""
    bucket = fail_msg
    # Remove stuff.
    for regex in _REGEX_REMOVE:
        bucket = regex.sub("", bucket)
    # Strip stuff.
    for regex in _REGEX_STRIP:
        bucket = regex.sub(r"\g<1>", bucket)
    # Replace with '*'.
    for regex in _REGEX_STAR:
        bucket = regex.sub("*", bucket)

    return bucket


class JobFailureOverview(BaseModel):
    """Overview of the Job failure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """Name of the job."""

    seed: int | None
    """Test seed."""

    line: int | None
    """Line number within the log if there is one."""

    log_context: Sequence[str]
    """Context within the log."""


class BucketedFailures(BaseModel):
    """Bucketed failed runs.

    The runs are grouped into failure buckets based on the error messages they
    reported. This makes it easier to see the classes of errors.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: Mapping[str, Sequence["JobFailureOverview"]]
    """Mapping of common error message strings to the full job failure summary."""

    @staticmethod
    def from_job_status(results: Sequence["CompletedJobStatus"]) -> "BucketedFailures":
        """Construct from CompletedJobStatus objects."""
        buckets = {}

        for job_status in results:
            if job_status.status in ["F", "K"]:
                bucket = _bucketize(job_status.fail_msg.message)

                if bucket not in buckets:
                    buckets[bucket] = []

                buckets[bucket].append(
                    JobFailureOverview(
                        name=job_status.full_name,
                        seed=job_status.seed,
                        line=job_status.fail_msg.line_number,
                        log_context=job_status.fail_msg.context,
                    ),
                )

        return BucketedFailures(
            buckets=buckets,
        )


class SimResults:
    """An object wrapping up a table of results for some tests.

    self.table is a list of Result objects, each of which
    corresponds to one or more runs of the test with a given name.

    self.buckets contains a dictionary accessed by the failure signature,
    holding all failing tests with the same signature.
    """

    def __init__(self, results: Sequence["CompletedJobStatus"]) -> None:
        self.table = []
        self.buckets: Mapping[str, JobFailureOverview] = {}

        self._name_to_row = {}

        for job_status in results:
            self._add_item(job_status=job_status)

    def _add_item(self, job_status: "CompletedJobStatus") -> None:
        """Recursively add a single item to the table of results."""
        # Runs get added to the table directly
        if job_status.target == "run":
            self._add_run(job_status)

    def _add_run(self, job_status: "CompletedJobStatus") -> None:
        """Add an entry to table for item."""
        row = self._name_to_row.get(job_status.name)
        if row is None:
            row = Result(
                job_status.name,
                job_runtime=job_status.job_runtime,
                simulated_time=job_status.simulated_time,
            )
            self.table.append(row)
            self._name_to_row[job_status.name] = row

        # Record the max job_runtime of all reseeds.
        elif job_status.job_runtime > row.job_runtime:
            row.job_runtime = job_status.job_runtime
            row.simulated_time = job_status.simulated_time

        if job_status.status == "P":
            row.passing += 1
        row.total += 1
