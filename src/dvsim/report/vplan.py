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
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import hjson

from dvsim.logging import log

__all__ = ("VPlanInputs", "overall_coverage", "shell_command")

# Scratch subdirectory the annotated plan and its report are written to. Unchanged, so an existing
# link to the report still resolves
VPLAN_DIR = "cov_vplan"

ANNOTATED_HJSON = "vplan_annotated.hjson"
ANNOTATED_HTML = "vplan_annotated.html"
EVIDENCE_JSON = "dv_evidence.json"


@dataclass(frozen=True)
class VPlanInputs:
    """Everything the annotation needs, so this module never reaches back into a flow config."""

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
    prepare_opts: list[str] = field(default_factory=list)
    process_opts: list[str] = field(default_factory=list)

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


def shell_command(inputs: VPlanInputs) -> str:
    """Build the bash command that prepares and annotates the vPlan.

    Returned as one `bash -c` string because a scheduled job runs a shell command. `set -e` and the
    `&&` mean a broken annotation shows as a failed job rather than a silently missing score.
    """
    if shutil.which("dvplan") is None:
        # Warn and pass, so a checkout without dvplan does not fail every regression naming a vPlan
        warning = "WARNING: dvplan is not installed on PATH. Skipping vPlan annotation."
        return f"/usr/bin/env bash -c {shlex.quote(f'echo {shlex.quote(warning)}')}"

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

    script = (
        f"set -e; mkdir -p {shlex.quote(str(inputs.out_dir))}; "
        f"{shlex.join(prepare)} && {shlex.join(process)}"
    )
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
    """
    matches = sorted(glob.glob(pattern))  # noqa: PTH207 (Path.glob rejects an absolute pattern)
    if not matches:
        log.warning("No inspection records matched '%s', so none were annotated from.", pattern)
    return matches or [pattern]


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
