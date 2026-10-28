# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests for back-annotating a DVPlan verification plan after a regression.

The command built here is the interface to another tool, whose positional shape is a fixed
contract, so it is checked as carefully as anything that runs in this process. The rest covers
the promise that no vPlan problem can fail a regression that otherwise passed, and that the one
cfg mistake which can is caught while the jobs are still being built.
"""

from pathlib import Path

import pytest
from hamcrest import assert_that, contains_string, equal_to, is_, none

from dvsim.report.vplan import (
    ANNOTATED_HJSON,
    VPlanInputs,
    _expand,
    _process_command,
    overall_coverage,
    shell_command,
)


def _inputs(tmp_path: Path, **overrides: object) -> VPlanInputs:
    """Build the inputs for one annotation, overriding whatever a test cares about.

    Merged before the model is built rather than copied onto a built one, so an override goes
    through the same validation as the value it replaces.
    """
    base: dict[str, object] = {
        "vplan": tmp_path / "hw" / "ip" / "hmac" / "doc" / "hmac_vplan.hjson",
        "out_dir": tmp_path / "out",
        "dut_entity": "hmac",
        "dut_instance": "tb.dut",
        "cov_report_dir": Path("/scratch/hmac/cov_report"),
        "tool": "xcelium",
    }
    return VPlanInputs(**(base | overrides))


def test_the_command_keeps_dvplan_s_positional_contract(tmp_path: Path) -> None:
    """`process_results` takes its three positionals last, with `-s` as a flag before them.

    This pins what dvsim emits. It cannot check dvplan's side, which lives in another repo, so a
    failure here means the argv moved and the two need reconciling. Getting `-s` wrong is the
    error that reads as `--summary` swallowing the DUT name, hence pinning it rather than
    discovering it in a nightly.
    """
    inputs = _inputs(tmp_path)

    command = _process_command(inputs)

    assert_that(command[:2], equal_to(["dvplan", "process_results"]))
    # -s is a switch, and the three positionals follow it in order.
    assert_that(command[-4:], equal_to(["-s", "hmac", "tb.dut", str(inputs.annotated)]))


def test_every_coverage_source_reaches_one_invocation(tmp_path: Path) -> None:
    """The vendor report, the test results and the inspections annotate in a single run.

    dvplan writes a plan item off as unmeasurable only when none of the sources it was given can
    measure the item's field, so splitting these would lose whichever metric the first run lacked.
    """
    inspections = tmp_path / "inspections"
    inspections.mkdir()
    command = _process_command(_inputs(tmp_path, inspect=str(inspections)))

    joined = " ".join(command)
    assert_that(joined, contains_string("--coverage xcelium_report /scratch/hmac/cov_report"))
    assert_that(joined, contains_string("--coverage dv_evidence"))
    # One source, so the inspections ride along with the evidence rather than repeating the flag.
    assert_that(joined, contains_string(str(inspections)))
    assert_that(joined.count("--coverage"), equal_to(2))


def test_the_vendor_report_is_left_out_when_there_is_none(tmp_path: Path) -> None:
    """Without coverage the plan is still annotated, from the recorded evidence alone."""
    command = _process_command(_inputs(tmp_path, cov_report_dir=None))

    assert_that(" ".join(command), contains_string("--coverage dv_evidence"))
    assert_that("xcelium_report" in " ".join(command), is_(False))


def test_an_absolute_inspection_glob_expands(tmp_path: Path) -> None:
    """A cfg names inspections through `{proj_root}`, so the pattern is always absolute.

    `Path().glob` rejects an absolute pattern outright, so getting this wrong raises rather than
    degrading, which would take a passing regression down with it.
    """
    for name in ("reset", "security"):
        (tmp_path / f"{name}.inspect.json").write_text("{}", encoding="utf-8")

    matches = _expand(str(tmp_path / "*.inspect.json"))

    assert_that(
        matches,
        equal_to([str(tmp_path / "reset.inspect.json"), str(tmp_path / "security.inspect.json")]),
    )


def test_a_directory_of_inspections_is_passed_through(tmp_path: Path) -> None:
    """A path that exists needs no expansion, since dvplan reads a directory itself."""
    folder = tmp_path / "inspections"
    folder.mkdir()

    assert_that(_expand(str(folder)), equal_to([str(folder)]))


def test_a_pattern_matching_nothing_is_a_config_error(tmp_path: Path) -> None:
    """Naming inspections that do not exist is a cfg mistake, and both other answers are worse.

    Passing the pattern on would fail the job with dvplan's own message once the regression has
    already run, and dropping it would score the plan as though the cfg had never named any.
    """
    pattern = str(tmp_path / "nothing" / "*.json")

    with pytest.raises(ValueError, match="No inspection records matched"):
        _expand(pattern)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{hmac: {Normalized_Coverage: "82.5%"}}', 82.5),
        ("{hmac: {Normalized_Coverage: 82.5}}", 82.5),
        # A plan with no score annotated yet is not an error, it simply has none to report.
        ("{hmac: {Description: nothing scored}}", None),
        ("{}", None),
        ("not hjson at all {{{", None),
    ],
    ids=["percent_string", "bare_number", "no_score", "empty", "malformed"],
)
def test_the_overall_score_is_read_back_or_reported_as_absent(
    tmp_path: Path, content: str, expected: float | None
) -> None:
    """The score is quoted in the flow's report, so an unreadable plan must not raise."""
    annotated = tmp_path / ANNOTATED_HJSON
    annotated.write_text(content, encoding="utf-8")

    assert_that(overall_coverage(annotated), equal_to(expected))


def test_a_missing_annotated_plan_reports_no_score(tmp_path: Path) -> None:
    """Nothing was produced, so there is nothing to quote and nothing to raise about."""
    assert_that(overall_coverage(tmp_path / "absent.hjson"), is_(none()))


def test_a_missing_dvplan_is_decided_where_the_job_runs(tmp_path: Path) -> None:
    """A checkout without dvplan must not fail every regression that names a vPlan.

    Testing PATH here would answer for the host dvsim was launched from, which on a compute farm
    is not the host the job lands on, so the guard goes in the script and is checked there.
    """
    command = shell_command(_inputs(tmp_path))

    assert_that(command, contains_string("command -v dvplan"))
    assert_that(command, contains_string("WARNING"))
    assert_that(command, contains_string("exit 0"))


def test_the_command_fails_the_job_when_dvplan_does(tmp_path: Path) -> None:
    """A broken annotation shows as a failed job rather than a silently missing score.

    `set -e` and the `&&` are what carry a non-zero exit out to the scheduler, so they are
    checked rather than assumed.
    """
    command = shell_command(_inputs(tmp_path))

    assert_that(command, contains_string("set -e"))
    assert_that(command, contains_string("prepare_vplan"))
    assert_that(command, contains_string("&&"))
    assert_that(command, contains_string("process_results"))
