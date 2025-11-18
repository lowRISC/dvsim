# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Class describing simulation configuration object."""

import fnmatch
import re
import sys
from collections import OrderedDict, defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from dvsim.flow.base import FlowCfg
from dvsim.job.data import CompletedJobStatus
from dvsim.job.deploy import (
    CompileSim,
    CovAnalyze,
    CovMerge,
    CovReport,
    CovUnr,
    RunTest,
)
from dvsim.logging import log
from dvsim.modes import BuildMode, Mode, RunMode, find_mode
from dvsim.regression import Regression
from dvsim.report.data import FlowResults, IPMeta, Testpoint, TestResult, TestStage, ToolMeta
from dvsim.sim_results import SimResults
from dvsim.test import Test
from dvsim.testplan import Testplan
from dvsim.utils import TS_FORMAT, rm_path

# This affects the bucketizer failure report.
_MAX_UNIQUE_TESTS = 5
_MAX_TEST_RESEEDS = 2


class SimCfg(FlowCfg):
    """Simulation configuration object.

    A simulation configuration class holds key information required for building
    a DV regression framework.
    """

    flow = "sim"

    # TODO: Find a way to set these in sim cfg instead
    ignored_wildcards: ClassVar = [
        "build_mode",
        "index",
        "test",
        "seed",
        "svseed",
        "uvm_test",
        "uvm_test_seq",
        "cov_db_dirs",
        "sw_images",
        "sw_build_device",
        "sw_build_cmd",
        "sw_build_opts",
    ]

    def __init__(self, flow_cfg_file, hjson_data, args, mk_config) -> None:
        # Options set from command line
        self.tool = args.tool
        self.build_opts = []
        self.build_opts.extend(args.build_opts)
        self.en_build_modes = args.build_modes.copy()
        self.run_opts = []
        self.run_opts.extend(args.run_opts)
        self.en_run_modes = []
        self.en_run_modes.extend(args.run_modes)
        self.build_unique = args.build_unique
        self.build_seed = args.build_seed
        self.build_only = args.build_only
        self.run_only = args.run_only
        self.reseed_ovrd = args.reseed
        self.reseed_multiplier = args.reseed_multiplier
        # Waves must be of type string, since it may be used as substitution
        # variable in the HJson cfg files.
        self.waves = args.waves or "none"
        self.max_waves = args.max_waves
        self.cov = args.cov
        self.cov_merge_previous = args.cov_merge_previous
        self.profile = args.profile or "(cfg uses profile without --profile)"
        self.xprop_off = args.xprop_off
        self.no_rerun = args.no_rerun
        self.verbosity = None  # set in _expand
        self.verbose = args.verbose
        self.dry_run = args.dry_run
        self.map_full_testplan = args.map_full_testplan

        # Set default sim modes for unpacking
        if args.gui:
            self.en_build_modes.append("gui")
        if args.gui_debug:
            self.en_build_modes.append("gui_debug")
        if args.waves is not None:
            self.en_build_modes.append("waves")
        else:
            self.en_build_modes.append("waves_off")
        if self.cov is True:
            self.en_build_modes.append("cov")
        if args.profile is not None:
            self.en_build_modes.append("profile")
        if self.xprop_off is not True:
            self.en_build_modes.append("xprop")
        if self.build_seed:
            self.en_build_modes.append("build_seed")

        # Options built from cfg_file files
        self.project = ""
        self.flow = ""
        self.flow_makefile = ""
        self.pre_build_cmds = []
        self.post_build_cmds = []
        self.build_dir = ""
        self.pre_run_cmds = []
        self.post_run_cmds = []
        self.run_dir = ""
        self.sw_images = []
        self.sw_build_opts = []
        self.pass_patterns = []
        self.fail_patterns = []
        self.name = ""
        self.variant = ""
        self.dut = ""
        self.tb = ""
        self.testplan = ""
        self.fusesoc_core = ""
        self.ral_spec = ""
        self.build_modes = []
        self.run_modes = []
        self.regressions = []
        self.supported_wave_formats = None

        # Options from tools - for building and running tests
        self.build_cmd = ""
        self.flist_gen_cmd = ""
        self.flist_gen_opts = []
        self.flist_file = ""
        self.run_cmd = ""

        # Generated data structures
        self.variant_name = ""
        self.links = {}
        self.build_list = []
        self.run_list = []
        self.cov_merge_deploy = None
        self.cov_report_deploy = None
        self.results_summary = OrderedDict()

        super().__init__(flow_cfg_file, hjson_data, args, mk_config)

    def _expand(self) -> None:
        # Choose a wave format now. Note that this has to happen after parsing
        # the configuration format because our choice might depend on the
        # chosen tool.
        self.waves = self._resolve_waves()

        # If build_unique is set, then add current timestamp to uniquify it
        if self.build_unique:
            self.build_dir += "_" + self.timestamp

        # If the user specified a verbosity on the command line then
        # self.args.verbosity will be n, l, m, h or d. Set self.verbosity now.
        # We will actually have loaded some other verbosity level from the
        # config file, but that won't have any effect until expansion so we can
        # safely switch it out now.
        if self.args.verbosity is not None:
            self.verbosity = self.args.verbosity

        super()._expand()

        if self.variant:
            self.variant_name = self.name + "/" + self.variant
        else:
            self.variant_name = self.name

        # Set the title for simulation results.
        self.results_title = self.variant_name.upper() + " Simulation Results"

        # Stuff below only pertains to individual cfg (not primary cfg)
        # or individual selected cfgs (if select_cfgs is configured via command line)
        # TODO: find a better way to support select_cfgs
        if not self.is_primary_cfg and (not self.select_cfgs or self.name in self.select_cfgs):
            # If self.tool is None at this point, there was no --tool argument on
            # the command line, and there is no default tool set in the config
            # file. That's ok if this is a primary config (where the
            # sub-configurations can choose tools themselves), but not otherwise.
            if self.tool is None:
                log.error(
                    "Config file does not specify a default tool, "
                    "and there was no --tool argument on the command line.",
                )
                sys.exit(1)

            # Print scratch_path at the start:
            log.info("[scratch_path]: [%s] [%s]", self.name, self.scratch_path)

            # Set directories with links for ease of debug / triage.
            self.links = {
                "D": self.scratch_path + "/" + "dispatched",
                "P": self.scratch_path + "/" + "passed",
                "F": self.scratch_path + "/" + "failed",
                "K": self.scratch_path + "/" + "killed",
            }

            # Use the default build mode for tests that do not specify it
            if not hasattr(self, "build_mode"):
                self.build_mode = "default"

            # Set the primary build mode. The coverage associated to this build
            # is the main coverage. Some tools need this information. This is
            # of significance only when there are multiple builds. If there is
            # only one build, and its not the primary_build_mode, then we
            # update the primary_build_mode to match what is built.
            if not hasattr(self, "primary_build_mode"):
                self.primary_build_mode = self.build_mode

            # Create objects from raw dicts - build_modes, sim_modes, run_modes,
            # tests and regressions, only if not a primary cfg obj
            self._create_objects()

    def _resolve_waves(self):
        """Choose and return a wave format, if waves are enabled.

        This is called after reading the config file. This method is used to
        update the value of class member 'waves', which must be of type string,
        since it is used as a substitution variable in the parsed HJson dict.
        If waves are not enabled, or if this is a primary cfg, then return
        'none'. 'tool', which must be set at this point, supports a limited
        list of wave formats (supplied with 'supported_wave_formats' key).
        """
        if self.waves == "none" or self.is_primary_cfg:
            return "none"

        assert self.tool is not None

        # If the user has specified their preferred wave format, use it. As
        # a sanity check, error out if the chosen tool doesn't support the
        # format, but only if we know about the tool. If not, we'll just assume
        # they know what they're doing.
        if self.supported_wave_formats and self.waves not in self.supported_wave_formats:
            log.error(
                f"Chosen tool ({self.tool}) does not support wave format {self.waves!r}.",
            )
            sys.exit(1)

        return self.waves

    # Purge the output directories. This operates on self.
    def _purge(self) -> None:
        assert self.scratch_path
        log.info("Purging scratch path %s", self.scratch_path)
        rm_path(self.scratch_path)

    def _create_objects(self) -> None:
        # Create build and run modes objects
        self.build_modes = Mode.create_modes(BuildMode, self.build_modes)
        self.run_modes = Mode.create_modes(RunMode, self.run_modes)

        # Walk through build modes enabled on the CLI and append the opts
        for en_build_mode in self.en_build_modes:
            build_mode_obj = find_mode(en_build_mode, self.build_modes)
            if build_mode_obj is not None:
                self.pre_build_cmds.extend(build_mode_obj.pre_build_cmds)
                self.post_build_cmds.extend(build_mode_obj.post_build_cmds)
                self.build_opts.extend(build_mode_obj.build_opts)
                self.pre_run_cmds.extend(build_mode_obj.pre_run_cmds)
                self.post_run_cmds.extend(build_mode_obj.post_run_cmds)
                self.run_opts.extend(build_mode_obj.run_opts)
                self.sw_images.extend(build_mode_obj.sw_images)
                self.sw_build_opts.extend(build_mode_obj.sw_build_opts)
            else:
                log.error(
                    'Mode "%s" enabled on the command line is not defined',
                    en_build_mode,
                )
                sys.exit(1)

        # Walk through run modes enabled on the CLI and append the opts
        for en_run_mode in self.en_run_modes:
            run_mode_obj = find_mode(en_run_mode, self.run_modes)
            if run_mode_obj is not None:
                self.pre_run_cmds.extend(run_mode_obj.pre_run_cmds)
                self.post_run_cmds.extend(run_mode_obj.post_run_cmds)
                self.run_opts.extend(run_mode_obj.run_opts)
                self.sw_images.extend(run_mode_obj.sw_images)
                self.sw_build_opts.extend(run_mode_obj.sw_build_opts)
            else:
                log.error('Mode "%s" enabled on the command line is not defined', en_run_mode)
                sys.exit(1)

        # Create tests from given list of items
        self.tests = Test.create_tests(self.tests, self)

        # Regressions
        # Parse testplan if provided.
        if self.testplan != "":
            self.testplan = Testplan(
                self.testplan,
                repo_top=Path(self.proj_root),
                name=self.variant_name,
            )
            # Extract tests in each stage and add them as regression target.
            self.regressions.extend(self.testplan.get_stage_regressions())
        else:
            # Create a dummy testplan with no entries.
            self.testplan = Testplan(None, name=self.name)

        # Create regressions
        self.regressions = Regression.create_regressions(self.regressions, self, self.tests)

    def _print_list(self) -> None:
        for list_item in self.list_items:
            log.info("---- List of %s in %s ----", list_item, self.variant_name)
            items = getattr(self, list_item, None)
            if items is None:
                log.error("No %s defined for %s.", list_item, self.variant_name)

            for item in items:
                # Convert the item into something that can be printed in the
                # list. Some modes are specified as strings themselves (so
                # there's no conversion needed). Others should be subclasses of
                # Mode, which has a name field that we can use.
                if isinstance(item, str):
                    mode_name = item
                else:
                    assert isinstance(item, Mode)
                    mode_name = item.name

                log.info(mode_name)

    def _create_build_and_run_list(self) -> None:
        """Generate a list of deployable objects from the provided items.

        Tests to be run are provided with --items switch. These can be glob-
        style patterns. This method finds regressions and tests that match
        these patterns.
        """

        def _match_items(items: list, patterns: list):
            hits = []
            matched = set()
            for pattern in patterns:
                item_hits = fnmatch.filter(items, pattern)
                if item_hits:
                    hits += item_hits
                    matched.add(pattern)
            return hits, matched

        # Process regressions first.
        regr_map = {regr.name: regr for regr in self.regressions}
        regr_hits, items_matched = _match_items(regr_map.keys(), self.items)
        regrs = [regr_map[regr] for regr in regr_hits]
        for regr in regrs:
            overlap = bool([t for t in regr.tests if t in self.run_list])
            if overlap:
                log.warning(
                    f"Regression {regr.name} added to be run has tests that "
                    "overlap with other regressions also being run. This can "
                    "result in conflicting build / run time opts to be set, "
                    "resulting in unexpected results. Skipping.",
                )
                continue

            self.run_list += regr.tests
            # Merge regression's build and run opts with its tests and their
            # build_modes.
            regr.merge_regression_opts()

        # Process individual tests, skipping the ones already added from
        # regressions.
        test_map = {test.name: test for test in self.tests if test not in self.run_list}
        test_hits, items_matched_ = _match_items(test_map.keys(), self.items)
        self.run_list += [test_map[test] for test in test_hits]
        items_matched |= items_matched_

        # Check if all items have been processed.
        for item in set(self.items) - items_matched:
            log.warning(
                f"Item {item} did not match any regressions or tests in {self.flow_cfg_file}.",
            )

        # Merge the global build and run opts
        Test.merge_global_opts(
            self.run_list,
            self.pre_build_cmds,
            self.post_build_cmds,
            self.build_opts,
            self.pre_run_cmds,
            self.post_run_cmds,
            self.run_opts,
            self.sw_images,
            self.sw_build_opts,
        )

        # Process reseed override and create the build_list
        build_list_names = []
        for test in self.run_list:
            # Override reseed if available.
            if self.reseed_ovrd is not None:
                test.reseed = self.reseed_ovrd

            # Apply reseed multiplier if set on the command line. This is
            # always positive but might not be an integer. Round to nearest,
            # but make sure there's always at least one iteration.
            scaled = round(test.reseed * self.reseed_multiplier)
            test.reseed = max(1, scaled)

            # Create the unique set of builds needed.
            if test.build_mode.name not in build_list_names:
                self.build_list.append(test.build_mode)
                build_list_names.append(test.build_mode.name)

    def _create_dirs(self) -> None:
        """Create initial set of directories."""
        for link in self.links:
            rm_path(self.links[link])
            Path(self.links[link]).mkdir(parents=True)

    def _expand_run_list(self, build_map):
        """Generate a list of tests to be run.

        For each test in tests, we add it test.reseed times. The ordering is
        interleaved so that we run through all of the tests as soon as
        possible. If there are multiple tests and they have different reseed
        values, they are "fully interleaved" at the start (so if there are
        tests A, B with reseed values of 5 and 2, respectively, then the list
        will be ABABAAA).

        build_map is a dictionary mapping a build mode to a CompileSim object.
        """
        tagged = []

        for test in self.run_list:
            build_job = build_map[test.build_mode]
            tagged.extend((idx, RunTest(idx, test, build_job, self)) for idx in range(test.reseed))

        # Stably sort the tagged list by the 1st coordinate.
        tagged.sort(key=lambda x: x[0])

        # Return the sorted list of RunTest objects, discarding the indices by
        # which we sorted it.
        return [run for _, run in tagged]

    def _create_deploy_objects(self) -> None:
        """Create deploy objects from the build and run lists."""
        # Create the build and run list first
        self._create_build_and_run_list()

        self.builds = []
        build_map = {}
        for build_mode_obj in self.build_list:
            new_build = CompileSim(build_mode_obj, self)

            # It is possible for tests to supply different build modes, but
            # those builds may differ only under specific circumstances,
            # such as coverage being enabled. If coverage is not enabled,
            # then they may be completely identical. In that case, we can
            # save compute resources by removing the extra duplicated
            # builds. We discard the new_build if it is equivalent to an
            # existing one.
            is_unique = True
            for build in self.builds:
                if new_build.is_equivalent_job(build):
                    # Discard `new_build` since build implements the same
                    # thing. If `new_build` is the same as
                    # `primary_build_mode`, update `primary_build_mode` to
                    # match `build`.
                    if new_build.name == self.primary_build_mode:
                        self.primary_build_mode = build.name
                    new_build = build
                    is_unique = False
                    break

            if is_unique:
                self.builds.append(new_build)
            build_map[build_mode_obj] = new_build

        # If there is only one build, set primary_build_mode to it.
        if len(self.builds) == 1:
            self.primary_build_mode = self.builds[0].name

        # Check self.primary_build_mode is set correctly.
        build_mode_names = {b.name for b in self.builds}
        if self.primary_build_mode not in build_mode_names:
            log.error(
                f'"primary_build_mode: {self.primary_build_mode}" '
                f"in {self.name} cfg is invalid. Please pick from "
                f"{build_mode_names}.",
            )
            sys.exit(1)

        # Update all tests to use the updated (uniquified) build modes.
        for test in self.run_list:
            if test.build_mode.name != build_map[test.build_mode].name:
                test.build_mode = find_mode(build_map[test.build_mode].name, self.build_modes)

        self.runs = [] if self.build_only else self._expand_run_list(build_map)

        # In GUI mode or GUI with debug mode, only allow one test to run.
        if self.gui and len(self.runs) > 1:
            self.runs = self.runs[:1]
            log.warning(
                f"In GUI mode, only one test is allowed to run. Picking {self.runs[0].full_name}",
            )

        # GUI mode is only available for Xcelium for the moment.
        if (self.gui_debug) and (self.tool not in ["xcelium"]):
            log.error(
                "GUI debug mode is only available for Xcelium, please remove "
                "--gui_debug / -gd option or switch to Xcelium tool.",
            )
            sys.exit(1)

        # Add builds to the list of things to run, only if --run-only switch
        # is not passed.
        self.deploy = []
        if not self.run_only:
            self.deploy += self.builds

        if not self.build_only:
            self.deploy += self.runs

            # Create cov_merge and cov_report objects, so long as we've got at
            # least one run to do.
            if self.cov and self.runs:
                self.cov_merge_deploy = CovMerge(self.runs, self)
                self.cov_report_deploy = CovReport(self.cov_merge_deploy, self)
                self.deploy += [self.cov_merge_deploy, self.cov_report_deploy]

        # Create initial set of directories before kicking off the regression.
        self._create_dirs()

    def _cov_analyze(self) -> None:
        """Open GUI tool for coverage analysis.

        Use the last regression coverage data to open up the GUI tool to analyze
        the coverage.
        """
        # Create initial set of directories, such as dispatched, passed etc.
        self._create_dirs()

        cov_analyze_deploy = CovAnalyze(self)
        self.deploy = [cov_analyze_deploy]

    def cov_analyze(self) -> None:
        """Public facing API for analyzing coverage."""
        for item in self.cfgs:
            item._cov_analyze()

    def _cov_unr(self) -> None:
        """Generate unreachable coverage exclusions.

        Use the last regression coverage data to generate unreachable coverage
        exclusions.
        """
        # TODO, Only support VCS
        if self.tool not in ["vcs", "xcelium"]:
            log.error("Only VCS and Xcelium are supported for the UNR flow.")
            sys.exit(1)
        # Create initial set of directories, such as dispatched, passed etc.
        self._create_dirs()

        cov_unr_deploy = CovUnr(self)
        self.deploy = [cov_unr_deploy]

    def cov_unr(self) -> None:
        """Public facing API for analyzing coverage."""
        for item in self.cfgs:
            item._cov_unr()

    def _gen_json_results(self, run_results: Sequence[CompletedJobStatus]) -> FlowResults:
        """Generate structured FlowResults from simulation run data.

        Args:
            run_results: completed job status.

        Returns:
            Flow results object.

        """
        sim_results = SimResults(results=run_results)
        if not self.testplan.test_results_mapped:
            self.testplan.map_test_results(sim_results.table)

        # --- Metadata ---
        timestamp = datetime.strptime(self.timestamp, TS_FORMAT).replace(tzinfo=timezone.utc)

        commit_match = re.search(r"github.com/.+?/tree/([0-9a-f]{7,40})", self.revision)
        commit = commit_match.group(1) if commit_match else None

        block = IPMeta(
            name=self.name.lower(),
            variant=(self.variant or "").lower() or None,
            commit=commit or "",
            branch=self.branch or "",
            url=f"https://github.com/lowrisc/opentitan/tree/{commit}" if commit else "",
        )
        tool = ToolMeta(name=self.tool.lower(), version="unknown")

        # --- Build stages only from testpoints that have at least one executed test ---
        stage_to_tps: defaultdict[str, dict[str, Testpoint]] = defaultdict(dict)

        def make_test_result(tr) -> TestResult | None:
            if tr.total == 0 and not self.map_full_testplan:
                return None

            return TestResult(
                max_time=tr.job_runtime,
                sim_time=tr.simulated_time,
                passed=tr.passing,
                total=tr.total,
                percent=100.0 * tr.passing / (tr.total or 1),
            )

        # 1. Mapped testpoints — only include if at least one test ran
        for tp in self.testplan.testpoints:
            if tp.name in {"Unmapped tests", "N.A."}:
                continue

            test_results: dict[str, TestResult] = {}
            for tr in tp.test_results:
                if test := make_test_result(tr):
                    test_results[tr.name] = test

            # Critical: skip entire testpoint if no tests actually ran
            if not test_results and not self.map_full_testplan:
                continue

            # Aggregate testpoint stats
            tp_passed = sum(t.passed for t in test_results.values())
            tp_total = sum(t.total for t in test_results.values())

            stage_to_tps[tp.stage][tp.name] = Testpoint(
                tests=test_results,
                passed=tp_passed,
                total=tp_total,
                percent=100.0 * tp_passed / tp_total if tp_total else 0.0,
            )

        # 2. Unmapped tests — only if they actually ran
        unmapped_tests: dict[str, TestResult] = {}
        for tr in sim_results.table:
            if not tr.mapped and (test := make_test_result(tr)):
                unmapped_tests[tr.name] = test

        if unmapped_tests:
            tp_passed = sum(t.passed for t in unmapped_tests.values())
            tp_total = sum(t.total for t in unmapped_tests.values())
            stage_to_tps["unmapped"]["Unmapped"] = Testpoint(
                tests=unmapped_tests,
                passed=tp_passed,
                total=tp_total,
                percent=100.0 * tp_passed / tp_total if tp_total else 0.0,
            )

        # --- Final stage aggregation ---
        stages: dict[str, TestStage] = {}
        total_passed = total_runs = 0

        for stage_name, testpoints in stage_to_tps.items():
            stage_passed = stage_total = 0
            for tp in testpoints.values():
                stage_passed += tp.passed
                stage_total += tp.total

            stages[stage_name] = TestStage(
                testpoints=testpoints,
                passed=stage_passed,
                total=stage_total,
                percent=100.0 * stage_passed / stage_total if stage_total else 0.0,
            )

            total_passed += stage_passed
            total_runs += stage_total

        # --- Coverage ---
        coverage: dict[str, float | None] = {}
        if self.cov_report_deploy:
            for k, v in self.cov_report_deploy.cov_results_dict.items():
                try:
                    coverage[k.lower()] = float(v.rstrip("% "))
                except (ValueError, TypeError, AttributeError):
                    coverage[k.lower()] = None

        # --- Final result ---
        return FlowResults(
            block=block,
            tool=tool,
            timestamp=timestamp,
            stages=stages,
            coverage=coverage,
            passed=total_passed,
            total=total_runs,
            percent=100.0 * total_passed / total_runs if total_runs else 0.0,
        )
