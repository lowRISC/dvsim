# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Testpoint and Testplan classes for maintaining the testplan."""

import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

import hjson
from tabulate import tabulate


class Result:
    """The results for a job."""

    def __init__(
        self,
        name: str,
        *,
        passing: int = 0,
        total: int = 0,
        job_runtime_s: float | None = None,
        simulated_time_us: float | None = None,
    ) -> None:
        """Construct a Result with the given parameters.

        Args:
          name: The name of the test.

          passing: The number of runs that passed (possibly different seeds).

          total: The number of runs that happened (will be at least as large as
          passing).

          job_runtime_s: If not None, the number of seconds taken by the job.

          simulated_time_us: If not None, the simulated time in microseconds.

        """
        self.name = name
        self.passing = passing
        self.total = total
        self.job_runtime = job_runtime_s
        self.simulated_time = simulated_time_us
        self.mapped = False


class Element:
    """An element of the testplan.

    This is either a testpoint or a covergroup.
    """

    # Type of the testplan element. Must be set by the extended class.
    kind = "none"

    # Mandatory fields in a testplan element.
    fields = ["name", "desc"]

    def __init__(self, raw_dict) -> None:
        """Initialize the testplan element.

        raw_dict is the dictionary parsed from the Hjson file.
        """
        # 'tags' is an optional field in addition to the mandatory self.fields.
        self.tags = []

        for field in self.fields:
            try:
                setattr(self, field, raw_dict.pop(field))
            except KeyError as e:
                msg = (
                    f"Error: {self.kind} does not contain all of "
                    f"the required fields:\n{raw_dict}\nRequired:\n"
                    f"{self.fields}\n{e}"
                )
                raise KeyError(
                    msg,
                )

        # Set the remaining k-v pairs in raw_dict as instance attributes.
        for k, v in raw_dict.items():
            setattr(self, k, v)

        # Verify things are in order.
        self._validate()

    def _validate(self) -> None:
        """Runs some basic consistency checks."""
        if not self.name:
            msg = f"Error: {self.kind.capitalize()} name cannot be empty:\n{self}"
            raise ValueError(msg)

        # "tags", if updated key must be list.
        if not isinstance(self.tags, list):
            msg = f"'tags' key in {self} is not a list."
            raise ValueError(msg)

    def has_tags(self, tags: set[str]) -> bool:
        """Return true if the element matches the provided tags.

        The element should match every item in the set of tags. If one of these
        items is preceded with "-", the meaning is negated (so the element
        should not match the tag name).

        If tags is empty, this will vacuously return true.

        Args:
          tags: The set of named tags against which to match.

        """
        for tag in tags:
            if tag.startswith("-"):
                if tag[1:] in self.tags:
                    return False
            elif tag not in self.tags:
                return False

        return True


class Covergroup(Element):
    """A coverage model item.

    The list of covergroups defines the coverage model for the design. Each
    entry captures the name of the covergroup (suffixed with _cg) and a brief
    description describing what functionality is covered. It is recommended to
    include individual coverpoints and crosses in the description.
    """

    kind = "covergroup"

    def _validate(self) -> None:
        super()._validate()
        if not self.name.endswith("_cg"):
            msg = f'Error: Covergroup name {self.name} needs to end with suffix "_cg".'
            raise ValueError(
                msg,
            )


class Testpoint(Element):
    """An testcase entry in the testplan.

    A testpoint maps to a unique design feature that is planned to be verified.
    It captures following information:
    - name of the planned test
    - a brief description indicating intent, stimulus and checking procedure
    - the targeted stage
    - the list of actual developed tests that verify it
    """

    kind = "testpoint"
    fields = [*Element.fields, "stage", "tests"]

    # Verification stages.
    stages = ("N.A.", "V1", "V2", "V2S", "V3")

    def __init__(self, raw_dict) -> None:
        super().__init__(raw_dict)

        # List of Result objects indicating test results mapped to this
        # testpoint.
        self.test_results = []

        # If tests key is set to ["N/A"], then don't map this testpoint to the
        # simulation results.
        self.not_mapped = False
        if self.tests == ["N/A"]:
            self.not_mapped = True

    def _validate(self) -> None:
        super()._validate()
        if self.stage not in Testpoint.stages:
            msg = (
                f"Testpoint stage {self.stage} is invalid:\n{self}\nLegal values: Testpoint.stages"
            )
            raise ValueError(
                msg,
            )

        # "tests" key must be list.
        if not isinstance(self.tests, list):
            msg = f"'tests' key in {self} is not a list."
            raise ValueError(msg)

    @staticmethod
    def _expand_str(pattern: str, new_vals: Sequence[str], txt: str) -> list[str]:
        """Return a list of copies of txt with each expansion of pattern.

        Note that if txt has multiple copies of the pattern then they are
        replaced "diagonally". If pattern is "x", new_vals is ["0", "1"] and
        txt is "x x" then the result is ["0 0", "1 1"].

        Args:
          pattern: A string for which we should search.

          new_vals: A list of values to use as replacements.

          txt: The string in which to replace the given pattern.

        """
        return [txt.replace(pattern, v) for v in new_vals]

    @staticmethod
    def _expand_str_list(pattern: str, new_vals: Sequence[str], txt_list: list[str]) -> list[str]:
        """Return a each expansion of pattern across elements of txt_list.

        This works by calling _expand_str to expand pattern for each element of
        txt_list, collecting the list of results.

        Args:
          pattern: A string for which we should search.

          new_vals: A list of values to use as replacements.

          txt_list: List of strings to expand

        """
        ret: list[str] = []
        for txt in txt_list:
            ret.extend(Testpoint._expand_str(pattern, new_vals, txt))
        return ret

    def do_substitutions(
        self, substitutions: dict[str, Any], reserved_names: Sequence[str]
    ) -> None:
        """Substitute {wildcards} in tests.

        If tests have wildcards, they are substituted using key=value pairs
        from the substitutions argument.

        If a value in the substitutions argument is a list, the substitution
        will make multiple testpoints from a templated value. For example, if
        substitutions is {'a': ['x', 'y']} and self.tests is ['test-{a}'] then
        self.tests will become ['test-x', 'test-y'].

        A wildcard use with no match in substitutions will be replaced by an
        empty string (in a single item). For example, if substitutions is {}
        and self.tests is ['test-{a}'] then self.tests will become ['test-'].

        """
        resolved_tests = []
        for test in self.tests:
            # Iterate over all the wildcards found in the test name, creating a
            # map from wildcard string ("{my_wildcard}") to a list of strings.
            wildcard_expansions: dict[str, list[str]] = {}
            for key in re.findall(r"{([A-Za-z0-9\_]+)}", test):
                if key in reserved_names:
                    msg = f"Wildcard using reserved name, {key}."
                    raise ValueError(msg)

                raw_value = substitutions.get(key, [""])
                if isinstance(raw_value, list):
                    value = raw_value
                elif isinstance(raw_value, str):
                    value = [raw_value]
                else:
                    msg = f"Unknown type to replace wildcard {key}. Value was {raw_value}."
                    raise TypeError(msg)

                wildcard_expansions[f"{{{key}}}"] = value

            # Iterate over the expansions, applying each in turn.
            expanded = [test]
            for pattern, values in wildcard_expansions.items():
                expanded = Testpoint._expand_str_list(pattern, values, expanded)

            resolved_tests.extend(expanded)

        self.tests = resolved_tests

    def map_test_results(self, test_results: list[Result]) -> None:
        """Map test results to tests against this testpoint.

        Given a list of test results find the ones that match the tests listed
        in this testpoint and build a structure. If no match is found, or if
        self.tests is an empty list, indicate 0/1 passing so that it is
        factored into the final total.
        """
        # If no written tests were indicated for this testpoint, then reuse
        # the testpoint name to count towards "not run".
        if not self.tests:
            self.test_results = [Result(name=self.name)]
            return

        # Skip if this testpoint is not meant to be mapped to the simulation
        # results.
        if self.not_mapped:
            return

        for tr in test_results:
            if tr.name in self.tests:
                tr.mapped = True
                self.test_results.append(tr)

        # Did we map all tests in this testpoint? If we are mapping the full
        # testplan, then count the ones not found as "not run", i.e. 0 / 0.
        tests_mapped = [tr.name for tr in self.test_results]
        for test in self.tests:
            if test not in tests_mapped:
                self.test_results.append(Result(name=test))


class Testplan:
    """The full testplan.

    The list of Testpoints and Covergroups make up the testplan.
    """

    @staticmethod
    def _parse_hjson(filename: Path) -> dict[str, Any]:
        """Parse an Hjson file at the given path and return it as a dict."""
        return hjson.loads(Path(filename).read_text(encoding="utf-8"))

    @staticmethod
    def _check_duplicates(kind: str, elements: Sequence[Element]) -> None:
        """Check that there aren't multiple elements in the list that share a name.

        Args:
          kind: A string describing the type of object (for use in error messages)

          elements: The list of elements to check for duplicates

        """
        known_names: set[str] = set()
        for elem in elements:
            if elem.name in known_names:
                msg = f"Duplicate {kind} items with name {elem.name}"
                raise ValueError(msg)
            known_names.add(elem.name)

    @staticmethod
    def _get_percentage(value: int, total: int) -> str:
        """Format a fraction (value / total) as a float with up to 2 decimal places.

        Both arguments should be non-negative and value should be at most equal
        to total. If total is zero, this is reported as "-- %".

        """
        if value > total:
            raise ValueError("Cannot represent fraction over 100%")
        if value < 0:
            raise ValueError("Cannot represent negative fraction")

        return "-- %" if total == 0 else f"{100 * value / total:.2f} %"

    def __init__(self, tagged_filename: str, repo_top: Path, name: str) -> None:
        """Initialize the testplan.

        Args:
          tagged_filename: Describes the Hjson file that captures the testplan.
                           This is a string, rather than a Path object, because
                           it may be suffixed with tags separated with a colon
                           delimiter to filter the testpoints.

                           For example: "path/to/foo_testplan.hjson:bar:baz"

          repo_top:        The path to the top level repo / project directory.
                           This is combined with the filename argument.

          name:            The name of the testplan / DUT. It overrides any
                           name set in the testplan Hjson.

        """
        self.name = None
        self.testpoints: list[Testpoint] = []
        self.covergroups: list[Covergroup] = []
        self.test_results_mapped = False

        # Split the filename into filename and tags, if provided.
        split = tagged_filename.split(":")
        filename = Path(split[0])
        tags = set(split[1:])

        if filename.exists():
            try:
                self._parse_testplan(filename, tags, repo_top)
            except Exception as e:
                msg = f"Error when parsing testplan at {filename}."
                raise RuntimeError(msg) from e

        # Represents current progress towards each stage. Stage = N.A.
        # is used to indicate the unmapped tests.
        self.progress = {}
        for key in Testpoint.stages:
            self.progress[key] = {
                "total": 0,
                "written": 0,
                "passing": 0,
                "progress": 0.0,
            }

    @staticmethod
    def _get_imported_testplan_paths(
        parent_testplan: Path,
        imported_testplans: list,
        repo_top: Path,
    ) -> list:
        """Parse imported testplans with correctly set paths.

        Paths of the imported testplans can be set relative to repo_top
        or relative to the parent testplan importing it. Path anchored to
        the repo_top has higher precedence. If the path is not relative to
        either, we check if the path is absolute (which must be avoided!),
        else we raise an exception.

        parent_testplan is the testplan currently being processed which
        importing the sub-testplans.
        imported_testplans is the list of testplans it imports - retrieved
        directly from its Hjson file.
        repo_top is the path to the repository's root directory.

        Returns a list of imported testplans with correctly set paths.
        Raises FileNotFoundError if the relative path to the testplan is
        not anchored to repo_top or the parent testplan.
        """
        result = []
        for testplan in imported_testplans:
            path = repo_top / testplan
            if path.exists():
                result.append(path)
                continue

            path = parent_testplan.parent / testplan
            if path.exists():
                result.append(path)
                continue

            # In version-controlled codebases, references to absolute paths
            # must not exist. This usecase is supported anyway.
            path = Path(testplan)
            if path.exists():
                result.append(path)
                continue

            msg = f"Testplan {testplan} imported by {parent_testplan} does not exist."
            raise FileNotFoundError(
                msg,
            )

        return result

    def _parse_testplan(self, filename: Path, tags: set[str], repo_top: Path) -> None:
        """Parse testplan Hjson file and create the testplan elements.

        It creates the list of testpoints and covergroups extracted from the
        file.

        filename is the path to the testplan file written in Hjson format.
        repo_top is an optional argument indicating the path to repo top.
        """
        obj = Testplan._parse_hjson(filename)

        parsed = set()
        parent_testplan = Path(filename)
        imported_testplans = self._get_imported_testplan_paths(
            parent_testplan,
            obj.get("import_testplans", []),
            repo_top,
        )

        while imported_testplans:
            testplan = imported_testplans.pop(0)
            if testplan in parsed:
                sys.exit(1)
            parsed.add(testplan)
            data = self._parse_hjson(repo_top / testplan)
            imported_testplans.extend(
                self._get_imported_testplan_paths(
                    testplan,
                    data.get("import_testplans", []),
                    repo_top,
                ),
            )
            obj = _merge_dicts(obj, data)

        self.name = obj.get("name")

        all_tps = [Testpoint(t) for t in obj.get("testpoints", [])]
        all_cgs = [Covergroup(cg) for cg in obj.get("covergroups", [])]

        if not (all_tps or all_cgs):
            raise ValueError("Merged testplan doesn't contain any testpoints or covergroups")

        Testplan._check_duplicates("testpoint", all_tps)
        Testplan._check_duplicates("covergroup", all_cgs)

        # Wildcards in testpoints can mostly point to any value from the
        # object. The following names are *not* allowed (because they wouldn't
        # really make much sense).
        reserved_names = ("import_testplans", "testpoints", "covergroups")

        # Apply wildcards in each testpoint
        for tp in self.testpoints:
            tp.do_substitutions(obj, reserved_names)

        self._sort()

    def _sort(self) -> None:
        """Sort testpoints by stage and covergroups by name."""
        self.testpoints.sort(key=lambda x: x.stage)
        self.covergroups.sort(key=lambda x: x.name)

    def get_stage_regressions(self):
        regressions = defaultdict(set)
        for tp in self.testpoints:
            if tp.not_mapped:
                continue
            if tp.stage in tp.stages[1:]:
                regressions[tp.stage].update({t for t in tp.tests if t})

        # Build regressions dict into a Hjson-like data structure
        return [{"name": ms, "tests": list(regressions[ms])} for ms in regressions]

    def write_testplan_doc(self, output: TextIO) -> None:
        """Write testplan documentation in markdown from the Hjson testplan."""
        stages = {}
        for tp in self.testpoints:
            stages.setdefault(tp.stage, []).append(tp)

        output.write("# Testplan\n\n## Testpoints\n\n")
        for stage, testpoints in stages.items():
            output.write(f"### Stage {stage} Testpoints\n\n")
            for tp in testpoints:
                output.write(f"#### `{tp.name}`\n\n")
                if len(tp.tests) == 0:
                    output.write("No Tests Implemented")
                elif len(tp.tests) == 1:
                    output.write(f"Test: `{tp.tests[0]}`")
                else:
                    output.write("Tests:\n")
                    output.writelines([f"- `{test}`\n" for test in tp.tests])

                output.write("\n\n" + tp.desc.strip() + "\n\n")

        if self.covergroups:
            output.write("## Covergroups\n\n")
            output.writelines(
                f"### {covergroup.name}\n\n{covergroup.desc.strip()}\n\n"
                for covergroup in self.covergroups
            )

    def map_test_results(self, test_results) -> None:
        """Map test results to testpoints."""
        # Maintain a list of tests we already counted.
        tests_seen = set()

        def _process_testpoint(testpoint, totals) -> None:
            """Computes the testplan progress and the sim footprint.

            totals is a list of Testpoint items that represent the total number
            of tests passing for each stage. The sim footprint is simply
            the sum total of all tests run in the simulation, counted for each
            stage and also the grand total.
            """
            ms = testpoint.stage
            for tr in testpoint.test_results:
                if not tr:
                    continue

                if tr.name in tests_seen:
                    continue

                tests_seen.add(tr.name)
                # Compute the testplan progress.
                self.progress[ms]["total"] += 1
                if tr.total != 0:
                    if tr.passing == tr.total:
                        self.progress[ms]["passing"] += 1
                    self.progress[ms]["written"] += 1

                # Compute the stage total & the grand total.
                totals[ms].test_results[0].passing += tr.passing
                totals[ms].test_results[0].total += tr.total
                if ms != "N.A.":
                    totals["N.A."].test_results[0].passing += tr.passing
                    totals["N.A."].test_results[0].total += tr.total

        totals = {}
        # Create testpoints to represent the total for each stage & the
        # grand total.
        for ms in Testpoint.stages:
            arg = {
                "name": "N.A.",
                "desc": f"Total {ms} tests",
                "stage": ms,
                "tests": [],
            }
            totals[ms] = Testpoint(arg)
            totals[ms].test_results = [Result("**TOTAL**")]

        # Create unmapped as a testpoint to represent tests from the simulation
        # results that could not be mapped to the testpoints.
        arg = {
            "name": "Unmapped tests",
            "desc": "Unmapped tests",
            "stage": "N.A.",
            "tests": [],
        }
        unmapped = Testpoint(arg)

        # Now, map the simulation results to each testpoint.
        for tp in self.testpoints:
            tp.map_test_results(test_results)
            _process_testpoint(tp, totals)

        # If we do have unmapped tests, then count that too.
        unmapped.test_results = [tr for tr in test_results if not tr.mapped]
        _process_testpoint(unmapped, totals)

        # Add stage totals back into 'testpoints' and sort.
        for ms in Testpoint.stages[1:]:
            self.testpoints.append(totals[ms])
        self._sort()

        # Append unmapped and the grand total at the end.
        if unmapped.test_results:
            self.testpoints.append(unmapped)
        self.testpoints.append(totals["N.A."])

        # Compute the progress rate for each stage.
        for ms in Testpoint.stages:
            stat = self.progress[ms]

            # Remove stages that are not targeted.
            if stat["total"] == 0:
                self.progress.pop(ms)
                continue

            stat["progress"] = self._get_percentage(stat["passing"], stat["total"])

        self.test_results_mapped = True

    def map_covergroups(self, cgs_found) -> None:
        """Map the covergroups found from simulation to the testplan.

        For now, this does nothing more than 'check off' the covergroup
        found from the simulation results with the coverage model in the
        testplan by updating the progress dict.

        cgs_found is a list of covergroup names extracted from the coverage
        database after the simulation is run with coverage enabled.
        """
        if not self.covergroups:
            return

        written = 0
        total = 0
        for cg in self.covergroups:
            total += 1
            if cg.name in cgs_found:
                written += 1

        self.progress["Covergroups"] = {
            "total": total,
            "written": written,
            "passing": written,
            "progress": self._get_percentage(written, total),
        }

    def get_test_results_table(self, map_full_testplan=True):
        """Return the mapped test results into a markdown table."""
        assert self.test_results_mapped, "Have you invoked map_test_results()?"
        header = [
            "Stage",
            "Name",
            "Tests",
            "Max Job Runtime",
            "Simulated Time",
            "Passing",
            "Total",
            "Pass Rate",
        ]
        colalign = ("center",) * 2 + ("left",) + ("center",) * 5
        table = []
        for tp in self.testpoints:
            stage = "" if tp.stage == "N.A." else tp.stage
            tp_name = "" if tp.name == "N.A." else tp.name
            for tr in tp.test_results:
                if tr.total == 0 and not map_full_testplan:
                    continue
                pass_rate = self._get_percentage(tr.passing, tr.total)

                job_runtime = "" if tr.job_runtime is None else f"{tr.job_runtime:.3f}s"
                simulated_time = "" if tr.simulated_time is None else f"{tr.simulated_time:.3f}us"

                table.append(
                    [
                        stage,
                        tp_name,
                        tr.name,
                        job_runtime,
                        simulated_time,
                        tr.passing,
                        tr.total,
                        pass_rate,
                    ],
                )
                stage = ""
                tp_name = ""

        text = "\n### Test Results\n"
        text += tabulate(table, headers=header, tablefmt="pipe", colalign=colalign)
        text += "\n"
        return text

    def get_progress_table(self):
        """Returns the current progress of the effort towards the testplan."""
        assert self.test_results_mapped, "Have you invoked map_test_results()?"
        header = []
        table = []
        for key in self.progress:
            stat = self.progress[key]
            values = list(stat.values())
            if not header:
                header = ["Items"] + [k.capitalize() for k in stat]
            table.append([key, *values])

        text = "\n### Testplan Progress\n"
        colalign = ("center",) * len(header)
        text += tabulate(table, headers=header, tablefmt="pipe", colalign=colalign)
        text += "\n"
        return text

    def get_cov_results_table(self, cov_results):
        """Returns the coverage in a table format.

        cov_results is a list of dicts with name and result keys, representing
        the name of the coverage metric and the result in decimal / fp value.
        """
        if not cov_results:
            return ""

        try:
            cov_header = [c["name"].capitalize() for c in cov_results]
            cov_values = [c["result"] for c in cov_results]
        except KeyError:
            sys.exit(1)

        colalign = ("center",) * len(cov_header)
        text = "\n### Coverage Results\n"
        text += tabulate([cov_values], headers=cov_header, tablefmt="pipe", colalign=colalign)
        text += "\n"
        return text

    def get_test_results_summary(self):
        """Returns the final total as a summary."""
        assert self.test_results_mapped, "Have you invoked map_test_results()?"

        # The last item in testpoints is the final sum total. We use that to
        # return the results summary as a dict.
        total = self.testpoints[-1]
        assert total.name == "N.A."
        assert total.stage == "N.A."

        tr = total.test_results[0]

        result = {}
        result["Name"] = self.name.upper()
        result["Passing"] = tr.passing
        result["Total"] = tr.total
        result["Pass Rate"] = self._get_percentage(tr.passing, tr.total)
        return result

    def get_sim_results(self, sim_results_file: str, fmt="md"):
        """Returns the mapped sim result tables in HTML formatted text.

        The data extracted from the sim_results table Hjson file is mapped into
        a test results, test progress, covergroup progress and coverage tables.

        fmt is either 'md' (markdown) or 'html'.
        """
        assert fmt in ["md", "html"]
        sim_results = Testplan._parse_hjson(Path(sim_results_file))
        test_results_ = sim_results.get("test_results", None)

        test_results = []
        for item in test_results_:
            try:
                tr = Result(item["name"], passing=item["passing"], total=item["total"])
                test_results.append(tr)
            except KeyError:
                sys.exit(1)

        self.map_test_results(test_results)
        self.map_covergroups(sim_results.get("covergroups", []))

        text = "# Simulation Results\n"
        text += "## Run on {}\n".format(sim_results["timestamp"])
        text += self.get_test_results_table()
        text += self.get_progress_table()

        cov_results = sim_results.get("cov_results", [])
        text += self.get_cov_results_table(cov_results)

        return text


def _merge_dicts(list1, list2, use_list1_for_defaults=True):
    """Merge 2 dicts into one.

    This function takes 2 dicts as args list1 and list2. It recursively merges
    list2 into list1 and returns list1. The recursion happens when the
    value of a key in both lists is a dict. If the values of the same key in
    both lists (at the same tree level) are of dissimilar type, then there is a
    conflict and an error is thrown. If they are of the same scalar type, then
    the third arg "use_list1_for_defaults" is used to pick the final one.
    """
    for key, item2 in list2.items():
        item1 = list1.get(key)
        if item1 is None:
            list1[key] = item2
            continue

        # Both dictionaries have an entry for this key. Are they both lists? If
        # so, append.
        if isinstance(item1, list) and isinstance(item2, list):
            list1[key] = item1 + item2
            continue

        # Are they both dictionaries? If so, recurse.
        if isinstance(item1, dict) and isinstance(item2, dict):
            _merge_dicts(item1, item2)
            continue

        # We treat other types as atoms. If the types of the two items are
        # equal pick one or the other (based on use_list1_for_defaults).
        if isinstance(item1, type(item2)) and isinstance(item2, type(item1)):
            list1[key] = item1 if use_list1_for_defaults else item2
            continue

        # Oh no! We can't merge this.
        sys.exit(1)

    return list1
