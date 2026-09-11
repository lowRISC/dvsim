# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Back-annotate a DVPlan verification plan from a finished regression.

This module builds the command; `job.deploy.CovVPlan` runs it as a scheduled job, so the step gets
its own row in the job status table alongside build, run, cov_merge and cov_report.

Nothing happens at all unless the sim cfg names a `vplan`.
"""

import glob
import shlex
from collections.abc import Sequence
from pathlib import Path

import hjson
from pydantic import BaseModel, ConfigDict, Field

from dvsim.logging import log

__all__ = (
    "SKIP_WITHOUT_DVPLAN",
    "VPlanInputs",
    "evidence_log",
    "overall_coverage",
    "shell_command",
)

# Scratch subdirectory the annotated plan and its report are written to. Unchanged, so an existing
# link to the report still resolves
VPLAN_DIR = "cov_vplan"

ANNOTATED_HJSON = "vplan_annotated.hjson"
ANNOTATED_HTML = "vplan_annotated.html"
EVIDENCE_JSON = "dv_evidence.json"

# The runs are logged here as they finish, and the evidence file is assembled from it. Beside
# the file it feeds, so everything the vPlan step reads or writes is in one directory
EVIDENCE_LOG = "dv_evidence.jsonl"

# Whether dvplan is installed is decided by the script, on the machine the job lands on, rather
# than by dvsim on whichever host the run was launched from. Exits 0 so that a checkout without
# dvplan does not fail every regression that names a vPlan
SKIP_WITHOUT_DVPLAN = (
    "if ! command -v dvplan >/dev/null 2>&1; then "
    "echo 'WARNING: dvplan is not installed on PATH. Skipping vPlan annotation.'; exit 0; fi;"
)


class VPlanInputs(BaseModel):
    """Everything the annotation needs, so this module never reaches back into a flow config."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vplan: Path
    """The verification plan to annotate."""
    out_dir: Path
    """Where the annotated plan, its report and the evidence file are written."""
    dut_entity: str
    """Name of the DUT entity, as a vPlan addresses it."""
    dut_instance: str
    """Hierarchical path to the DUT in the testbench, such as `tb.dut`."""
    cov_report_dir: Path | None
    """The vendor coverage report to annotate from, if the run produced one."""
    tool: str
    """Simulator name, which selects the vendor report format."""
    inspect: str = ""
    """Where hand-written inspection records live, if the cfg names any. A path or a glob."""
    prepare_opts: list[str] = Field(default_factory=list)
    """Extra options for `prepare_vplan`, as the cfg wrote them."""
    process_opts: list[str] = Field(default_factory=list)
    """Extra options for `process_results`, as the cfg wrote them."""

    @property
    def annotated(self) -> Path:
        """Where the annotated plan is written."""
        return self.out_dir / ANNOTATED_HJSON

    @property
    def report(self) -> Path:
        """Where the plan's HTML report is written."""
        return self.out_dir / ANNOTATED_HTML

    @property
    def evidence(self) -> Path:
        """Where the regression's evidence file is written, and read back from."""
        return self.out_dir / EVIDENCE_JSON

    @property
    def evidence_log(self) -> Path:
        """Where the runs were logged as they finished, which the evidence file is built from."""
        return self.out_dir / EVIDENCE_LOG


def evidence_log(scratch_path: Path) -> Path:
    """Where one sim cfg's runs are logged, given that cfg's scratch directory.

    The runs are logged while the regression is still going and the vPlan job reads the log back
    when it starts, so both ends have to agree on this without either holding the other's config.
    """
    return scratch_path / VPLAN_DIR / EVIDENCE_LOG


def shell_command(inputs: VPlanInputs) -> str:
    """Build the bash command that prepares and annotates the vPlan.

    Returned as one `bash -c` string because a job is dispatched to a compute node as a single
    command, so both dvplan calls and the guard in front of them have to travel as one. `set -e`
    and the `&&` mean a broken annotation shows as a failed job rather than a silently missing
    score. The output directory is not created here: every launcher makes a job's `odir` before it
    runs the command.

    The command is the same whether or not dvplan is installed here, because here is not where it
    runs. See `SKIP_WITHOUT_DVPLAN`.
    """
    # The vPlan sits at <ip_root>/<something>/<vplan>, so its grandparent is the IP root that
    # `prepare_vplan` traces specifications against.
    ip_root = inputs.vplan.parent.parent
    prepare = [
        "dvplan",
        "prepare_vplan",
        *_opts(inputs.prepare_opts),
        str(ip_root),
        str(inputs.vplan),
        str(inputs.annotated),
    ]
    process = _process_command(inputs)

    script = f"set -e; {SKIP_WITHOUT_DVPLAN} {shlex.join(prepare)} && {shlex.join(process)}"
    return f"/usr/bin/env bash -c {shlex.quote(script)}"


def _process_command(inputs: VPlanInputs) -> list[str]:
    """Build the `process_results` invocation, with every coverage source it should read.

    Every source goes to one invocation on purpose: dvplan writes an item off as unmeasurable only
    when none of the sources given to it can measure its field, so a second run would find the
    items only its own source answers for already written off.
    """
    coverage: list[str] = []
    if inputs.cov_report_dir:
        coverage += ["--coverage", f"{inputs.tool}_report", str(inputs.cov_report_dir)]
    # One source for both: dvplan reads the testcase and inspection metrics out of the same format.
    # A glob is expanded here because the argv is built directly, with no shell to do it
    evidence = [str(inputs.evidence)]
    if inputs.inspect:
        evidence += _expand(inputs.inspect)
    coverage += ["--coverage", "dv_evidence", *evidence]
    return [
        "dvplan",
        "process_results",
        *_opts(inputs.process_opts),
        *coverage,
        "-R",
        str(inputs.report),
        "-s",
        inputs.dut_entity,
        inputs.dut_instance,
        str(inputs.annotated),
    ]


def _opts(opts: Sequence[str]) -> list[str]:
    """Split cfg-supplied options into argv entries, dropping empty ones.

    Two shapes turn up in real cfgs that a bare splat would pass to dvplan as literal arguments:
    `[""]` for "none", which argparse reads as an empty positional, and `["--milestone-depth 1"]`
    written as one string, which it reads as a single unknown flag. Split the way a shell would, so
    an option carrying a quoted value stays one argument.
    """
    return [token for opt in opts for token in shlex.split(opt)]


def _expand(pattern: str) -> list[str]:
    """Expand an inspection path, which may be a file, a directory or a glob pattern.

    A cfg naming inspections through `{proj_root}` always produces an absolute pattern, which
    `Path.glob` refuses, so this is one of the places the pathlib rule does not apply.

    A pattern matching nothing raises, because both other answers are worse: passing it through
    fails the job with dvplan's own message once the regression has already run, and dropping it
    scores the plan as though the cfg had never named inspections at all. The command is built
    while the jobs are, so this lands before a single test starts.
    """
    matches = sorted(glob.glob(pattern))  # noqa: PTH207 (Path.glob rejects an absolute pattern)
    if not matches:
        msg = f"No inspection records matched 'dvplan_inspect' pattern '{pattern}'."
        raise ValueError(msg)
    return matches


def overall_coverage(annotated: Path) -> float | None:
    """Read the plan's overall normalised coverage back out of the annotated vPlan."""
    if not annotated.is_file():
        log.warning("No annotated vPlan at '%s', so its score is not reported.", annotated)
        return None
    try:
        with annotated.open(encoding="utf-8") as f:
            data = hjson.load(f)
        # An HJSON vPlan is keyed by DUT name: {dut_name: {fields...}}.
        root = next(iter(data.values()), {})
        raw = root.get("Normalized_Coverage")
        if raw is None:
            return None
        return float(str(raw).rstrip(" %"))
    except (OSError, ValueError, AttributeError, hjson.HjsonDecodeError):
        log.exception("Could not read the vPlan score from '%s'.", annotated)
        return None
