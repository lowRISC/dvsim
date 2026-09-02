# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Test reporting a formal run.

The two methods under test are exercised on stand-ins rather than on a `FormalCfg`, because
building one needs a config tree, and between them they touch only the handful of attributes the
fakes below carry. The stand-ins borrow the real methods, so what runs is the shipped code.

The distinction the fakes preserve is the one that matters here: `get_coverage` runs on a child
cfg and `gen_results_summary` on the primary that renders the cross-cfg table. A test that drives
only the child cannot see whether a column name reaches the table at all.
"""

import logging
from collections.abc import Iterator

import pytest
from hamcrest import assert_that, contains_string, equal_to, has_length, is_not

from dvsim.flow.formal import FormalCfg

__all__ = ()

# The proof-completeness columns each engine measures, under the names its own report parser
# writes. Only stimuli is common, so neither set can stand in for the other.
JASPERGOLD = {"formal": "79.44 %", "stimuli": "96.06 %", "checker": "78.75 %"}
VCFORMAL = {"stimuli": "12.00 %", "coi": "34.00 %", "proof": "56.00 %"}

# What the VC Formal flow reports today: its fpv.tcl collects nothing, so the parser answers N/A
# under all three of its own column names. Kept distinct from VCFORMAL because all-N/A values
# coincide with the no-coverage fallback and cannot on their own show which branch ran.
VCFORMAL_COLLECTED_NOTHING = {"stimuli": "N/A", "coi": "N/A", "proof": "N/A"}

FALLBACK_HEADER = ["name", "pass_rate", "formal_cov", "stimuli_cov", "checker_cov"]


class FakeChildCfg:
    """A child cfg, carrying only what `get_coverage` reads and writes."""

    get_coverage = FormalCfg.get_coverage

    def __init__(self, name: str = "hmac") -> None:
        """Initialise a child cfg as `FormalCfg.__init__` leaves one."""
        self.name = name
        self.cov_header: list[str] = []
        self.summary_header = list(FALLBACK_HEADER)
        self.result_summary: dict[str, list[str]] = {}

    def report(self, result: dict[str, dict[str, str]]) -> list[str]:
        """Read a run's result the way `_gen_results_for_cfg` does, and return the summary row."""
        _, summary = self.get_coverage(result)
        self.result_summary[self.name] = [self.name, "89.36 %", *summary]
        return summary


class FakePrimaryCfg:
    """A primary cfg, carrying only what `gen_results_summary` reads."""

    formal_cfgs = FormalCfg.formal_cfgs
    gen_results_summary = FormalCfg.gen_results_summary
    resolve_summary_header = FormalCfg.resolve_summary_header

    def __init__(self, cfgs: list[FakeChildCfg]) -> None:
        """Initialise a primary cfg over already-reported children."""
        self.name = "top_earlgrey_fpv_ip"
        self.cfgs = cfgs
        self.summary_header = list(FALLBACK_HEADER)
        self.results_title = "TOP_EARLGREY_FPV_IP Formal FPV Results"
        self.timestamp_long = "timestamp"
        self.revision = ""
        self.branch = "master"
        self.results_summary_md = ""


@pytest.fixture
def dvsim_log(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture dvsim's own logger, which deliberately does not propagate."""
    logger = logging.getLogger("dvsim")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.ERROR, logger="dvsim")
    yield caplog
    logger.removeHandler(caplog.handler)


def reported(*results: dict[str, dict[str, str]]) -> FakePrimaryCfg:
    """Return a primary cfg whose children have each reported one run."""
    children = []
    for index, result in enumerate(results):
        child = FakeChildCfg(name=f"cfg{index}")
        child.report(result)
        children.append(child)
    return FakePrimaryCfg(children)


class TestCoverageColumns:
    """Test that a run's own coverage columns are what gets reported."""

    @staticmethod
    @pytest.mark.parametrize(
        ("engine", "coverage"),
        [("jaspergold", JASPERGOLD), ("vcformal", VCFORMAL)],
    )
    def test_reports_the_columns_a_run_measured(
        engine: str,
        coverage: dict[str, str],
    ) -> None:
        """Naming the columns in dvsim fixed one engine's vocabulary and raised KeyError."""
        results_str, summary = FakeChildCfg().get_coverage({"coverage": coverage})

        assert_that(summary, equal_to(list(coverage.values())), engine)
        for column in coverage:
            assert_that(results_str, contains_string(column), engine)

    @staticmethod
    def test_records_the_columns_for_the_table_the_primary_cfg_renders() -> None:
        """The child is where the columns are known and the primary is where they are needed."""
        child = FakeChildCfg()

        child.get_coverage({"coverage": VCFORMAL})

        assert_that(child.cov_header, equal_to(["stimuli", "coi", "proof"]))

    @staticmethod
    def test_says_so_when_a_run_measured_no_coverage() -> None:
        """A formal flow that collects nothing leaves the key out entirely."""
        results_str, summary = FakeChildCfg().get_coverage({})

        assert_that(results_str, contains_string("No coverage information found"))
        assert_that(summary, equal_to(["N/A", "N/A", "N/A"]))

    @staticmethod
    def test_says_so_when_a_run_reported_no_columns() -> None:
        """An empty coverage key measured nothing, so it reports as nothing rather than as a row.

        Falling through would tabulate an empty table and contribute no cells at all to a summary
        row, leaving it short of the header instead of saying the run collected nothing.
        """
        child = FakeChildCfg()

        results_str, summary = child.get_coverage({"coverage": {}})

        assert_that(results_str, contains_string("No coverage information found"))
        assert_that(summary, equal_to(["N/A", "N/A", "N/A"]))
        assert_that(child.cov_header, equal_to([]))


class TestSummaryTable:
    """Test the cross-cfg summary table, which is where a column name is finally read."""

    @staticmethod
    @pytest.mark.parametrize(
        ("engine", "coverage", "columns"),
        [
            ("jaspergold", JASPERGOLD, ["formal_cov", "stimuli_cov", "checker_cov"]),
            ("vcformal", VCFORMAL, ["stimuli_cov", "coi_cov", "proof_cov"]),
            (
                "vcformal collecting nothing",
                VCFORMAL_COLLECTED_NOTHING,
                ["stimuli_cov", "coi_cov", "proof_cov"],
            ),
        ],
    )
    def test_names_the_columns_the_cfgs_tool_measured(
        engine: str,
        coverage: dict[str, str],
        columns: list[str],
    ) -> None:
        """Recording the header on the child alone left this table naming another engine's columns.

        `get_coverage` runs on the child and this table is rendered by the primary, so a header
        set on the child never reached it and VC Formal's stimuli, coi and proof figures were
        printed under JasperGold's formal, stimuli and checker headings. Both engines report three
        columns, so nothing misaligned and nothing failed.
        """
        primary = reported({"coverage": coverage})

        table = primary.gen_results_summary()

        assert_that(primary.summary_header, equal_to(["name", "pass_rate", *columns]), engine)
        for value in coverage.values():
            assert_that(table, contains_string(value), engine)

    @staticmethod
    def test_keeps_the_fallback_header_when_no_cfg_measured_coverage() -> None:
        """Nothing to follow, so the header stays as `__init__` set it."""
        primary = reported({})

        primary.gen_results_summary()

        assert_that(primary.summary_header, equal_to(FALLBACK_HEADER))

    @staticmethod
    def test_reports_cfgs_that_measured_different_columns(
        dvsim_log: pytest.LogCaptureFixture,
    ) -> None:
        """One table cannot carry two vocabularies, so a clash is said rather than resolved.

        A single `-t` makes every cfg in a run share an engine today. This is what says so if
        that ever stops being true, instead of labelling one engine's figures with the other's
        column names.
        """
        primary = reported({"coverage": JASPERGOLD}, {"coverage": VCFORMAL})

        primary.gen_results_summary()

        assert_that(dvsim_log.text, contains_string("different coverage columns"))
        assert_that(primary.summary_header, has_length(len(FALLBACK_HEADER)))

    @staticmethod
    def test_a_cfg_missing_its_results_stays_aligned_with_the_header(
        dvsim_log: pytest.LogCaptureFixture,
    ) -> None:
        """The placeholder row follows the header's width rather than assuming three columns."""
        primary = reported({"coverage": VCFORMAL})
        primary.cfgs[0].result_summary.clear()

        table = primary.gen_results_summary()

        assert_that(dvsim_log.text, contains_string("could not find generated results_summary"))
        assert_that(table, contains_string("ERROR"))
        assert_that(table, is_not(contains_string("formal_cov")))
