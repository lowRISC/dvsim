# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Job deployment mechanism."""

import pprint
import random
import shlex
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from tabulate import tabulate

from dvsim.job.data import JobSpec, WorkspaceConfig
from dvsim.job.time import JobTime
from dvsim.launcher.base import Launcher
from dvsim.logging import log
from dvsim.tool.utils import get_sim_tool_plugin
from dvsim.utils import (
    clean_odirs,
    find_and_substitute_wildcards,
    rm_path,
    subst_wildcards,
)

if TYPE_CHECKING:
    from dvsim.flow.sim import SimCfg
    from dvsim.modes import BuildMode


__all__ = (
    "CompileSim",
    "Deploy",
)


class Deploy:
    """Abstraction to create and maintain a runnable job (builds, runs, etc.)."""

    # Indicate the target for each sub-class.
    target = "none"

    # List of variable names that are to be treated as "list of commands".
    # This tells '_construct_cmd' that these vars are lists that need to
    # be joined with '&&' instead of a space.
    cmds_list_vars: ClassVar = []

    # Represents the weight with which a job of this target is scheduled. These
    # initial weights set for each of the targets below are roughly inversely
    # proportional to their average runtimes. These are subject to change in
    # future. Lower the runtime, the higher chance the it gets scheduled. It is
    # useful to customize this only in case of targets that may coexist at a
    # time.
    # TODO: Allow these to be set in the HJson.
    weight = 1

    def __str__(self) -> str:
        """Get a string representation of the deployment object."""
        return pprint.pformat(self.__dict__) if log.isEnabledFor(log.VERBOSE) else self.full_name

    def __init__(self, sim_cfg: "SimCfg") -> None:
        """Initialise deployment object.

        Args:
            sim_cfg: simulation config object

        """
        if self.target is None:
            raise RuntimeError("No target specified")

        # Cross ref the whole cfg object for ease.
        self.sim_cfg = sim_cfg
        self.flow = sim_cfg.name
        self._variant_suffix = f"_{self.sim_cfg.variant}" if self.sim_cfg.variant else ""

        # A list of jobs on which this job depends.
        self.dependencies = []

        # Indicates whether running this job requires all dependencies to pass.
        # If this flag is set to False, any passing dependency will trigger
        # this current job to run
        self.needs_all_dependencies_passing = True

        # Declare attributes that need to be extracted from the HJSon cfg.
        self._define_attrs()

        # Set class instance attributes.
        self._set_attrs()

        # Check if all attributes that are needed are set.
        self._check_attrs()

        # Do variable substitutions.
        self._subst_vars()

        # List of vars required to be exported to sub-shell, as a dict.
        self.exports = self._process_exports()

        # Construct the job's command.
        self.cmd = self._construct_cmd()

        self.workspace_cfg = WorkspaceConfig(
            project=sim_cfg.name,
            project_root=sim_cfg.proj_root,
            scratch_root=Path(sim_cfg.scratch_root),
            scratch_path=Path(sim_cfg.scratch_path),
            timestamp=sim_cfg.args.timestamp,
        )

    def get_job_spec(self) -> "JobSpec":
        """Get the job spec for this deployment."""
        return JobSpec(
            job_type=self.__class__.__name__,
            target=self.target,
            flow=self.flow,
            tool=self.sim_cfg.tool,
            name=self.name,
            seed=getattr(self, "seed", None),
            full_name=self.full_name,
            qual_name=self.qual_name,
            workspace_cfg=self.workspace_cfg,
            dependencies=[d.full_name for d in self.dependencies],
            weight=self.weight,
            timeout_mins=self.get_timeout_mins(),
            cmd=self.cmd,
            exports=self.exports,
            dry_run=self.dry_run,
            interactive=self.sim_cfg.interactive,
            gui=self.gui,
            needs_all_dependencies_passing=self.needs_all_dependencies_passing,
            pre_launch=self.pre_launch(),
            post_finish=self.post_finish(),
            odir=self.odir,
            links=self.sim_cfg.links,
            log_path=Path(f"{self.odir}/{self.target}.log"),
            pass_patterns=self.pass_patterns,
            fail_patterns=self.fail_patterns,
        )

    def _define_attrs(self) -> None:
        """Define the attributes this instance needs to have.

        These attributes are extracted from the Mode object / HJson config with
        which this instance is created. There are two types of attributes -
        one contributes to the generation of the command directly; the other
        provides supplementary information pertaining to the job, such as
        patterns that determine whether it passed or failed. These are
        represented as dicts, whose values indicate in boolean whether the
        extraction was successful.
        """
        # These attributes are explicitly used to construct the job command.
        self.mandatory_cmd_attrs = {}

        # These attributes may indirectly contribute to the construction of the
        # command (through substitution vars) or other things such as pass /
        # fail patterns.
        self.mandatory_misc_attrs = {
            "build_mode": False,
            "dry_run": False,
            "exports": False,
            "flow_makefile": False,
            "name": False,
        }

    # Function to parse a dict and extract the mandatory cmd and misc attrs.
    def _extract_attrs(self, ddict: Mapping) -> None:
        """Extract the attributes from the supplied dict.

        'ddict' is typically either the Mode object or the entire config
        object's dict. It is used to retrieve the instance attributes defined
        in 'mandatory_cmd_attrs' and 'mandatory_misc_attrs'.
        """
        ddict_keys = ddict.keys()
        for key in self.mandatory_cmd_attrs:
            if self.mandatory_cmd_attrs[key] is False and key in ddict_keys:
                setattr(self, key, ddict[key])
                self.mandatory_cmd_attrs[key] = True

        for key in self.mandatory_misc_attrs:
            if self.mandatory_misc_attrs[key] is False and key in ddict_keys:
                setattr(self, key, ddict[key])
                self.mandatory_misc_attrs[key] = True

    def _set_attrs(self) -> None:
        """Set additional attributes.

        Invokes '_extract_attrs()' to read in all the necessary instance
        attributes. Based on those, some additional instance attributes may
        be derived. Those are set by this method.
        """
        self._extract_attrs(self.sim_cfg.__dict__)

        # Enable GUI mode, also when GUI debug mode has been invoked.
        self.gui = self.sim_cfg.gui

        # Output directory where the artifacts go (used by the launcher).
        self.odir = getattr(self, self.target + "_dir")

        # Qualified name disambiguates the instance name with other instances
        # of the same class (example: 'uart_smoke' reseeded multiple times
        # needs to be disambiguated using the index -> '0.uart_smoke'.
        self.qual_name = self.name

        # Full name disambiguates across multiple cfg being run (example:
        # 'aes:default', 'uart:default' builds.
        self.full_name = f"{self.sim_cfg.name}{self._variant_suffix}:{self.qual_name}"

        # Job name is used to group the job by cfg and target. The scratch path
        # directory name is assumed to be uniquified, in case there are more
        # than one sim_cfgs with the same name.
        self.job_name = f"{Path(self.sim_cfg.scratch_path).name}_{self.target}"

        # Input directories (other than self) this job depends on.
        self.input_dirs = []

        # Directories touched by this job. These directories are marked
        # because they are used by dependent jobs as input.
        self.output_dirs = [self.odir]

        # Pass and fail patterns.
        self.pass_patterns = []
        self.fail_patterns = []

    def _check_attrs(self) -> None:
        """Check if all required class attributes are set.

        Invoked in __init__() after all attributes are extracted and set.
        """
        for attr in self.mandatory_cmd_attrs:
            if self.mandatory_cmd_attrs[attr] is False:
                msg = f"Attribute {attr!r} not found for {self.name!r}."
                raise AttributeError(
                    msg,
                )

        for attr in self.mandatory_misc_attrs:
            if self.mandatory_misc_attrs[attr] is False:
                msg = f"Attribute {attr!r} not found for {self.name!r}."
                raise AttributeError(
                    msg,
                )

    def _subst_vars(self, ignored_subst_vars=None) -> None:
        """Recursively search and replace substitution variables.

        First pass: search within self dict. We ignore errors since some
        substitutions may be available in the second pass. Second pass: search
        the entire sim_cfg object.
        """
        self.__dict__ = find_and_substitute_wildcards(
            obj=self.__dict__,
            wildcard_values=self.__dict__,
            ignored_wildcards=ignored_subst_vars,
            ignore_error=True,
        )
        self.__dict__ = find_and_substitute_wildcards(
            obj=self.__dict__,
            wildcard_values=self.sim_cfg.__dict__,
            ignored_wildcards=ignored_subst_vars,
            ignore_error=False,
        )

    def _process_exports(self) -> Mapping:
        """Convert 'exports' as a list of dicts in the HJson to a dict.

        Exports is a list of key-value pairs that are to be exported to the
        subprocess' environment so that the tools can lookup those options.
        DVSim limits how the data is presented in the HJson (the value of a
        HJson member cannot be an object). This method converts a list of dicts
        into a dict variable, which makes it easy to merge the list of exports
        with the subprocess' env where the ASIC tool is invoked.
        """
        return {k: str(v) for item in self.exports for k, v in item.items()}

    def _construct_cmd(self) -> str:
        """Construct the command that will eventually be launched."""
        cmd = f"make -f {self.flow_makefile} {self.target}"
        if self.dry_run is True:
            cmd += " -n"
        for attr in sorted(self.mandatory_cmd_attrs.keys()):
            value = getattr(self, attr)
            if type(value) is list:
                # Join attributes that are list of commands with '&&' to chain
                # them together when executed as a Make target's recipe.
                separator = " && " if attr in self.cmds_list_vars else " "
                value = separator.join(item.strip() for item in value)
            if type(value) is bool:
                value = int(value)
            if type(value) is str:
                value = shlex.quote(value.strip())
            cmd += f" {attr}={value}"
        return cmd

    def is_equivalent_job(self, item: "Deploy") -> bool:
        """Check if Deploy object results in an equivalent dispatched job.

        Determines if 'item' and 'self' would behave exactly the same way when
        deployed. If so, then there is no point in keeping both. The caller can
        choose to discard 'item' and pick 'self' instead. To do so, we check
        the final resolved 'cmd' & the exports. The 'name' field will be unique
        to 'item' and 'self', so we take that out of the comparison.
        """
        if not isinstance(item, Deploy):
            return False

        # Check if the cmd field is identical.
        item_cmd = item.cmd.replace(item.name, self.name)
        if self.cmd != item_cmd:
            return False

        # Check if exports have identical set of keys.
        if self.exports.keys() != item.exports.keys():
            return False

        # Check if exports have identical values.
        for key, val in self.exports.items():
            item_val = item.exports[key]
            if type(item_val) is str:
                item_val = item_val.replace(item.name, self.name)
            if val != item_val:
                return False

        log.verbose('Deploy job "%s" is equivalent to "%s"', item.name, self.name)
        return True

    def pre_launch(self) -> Callable[[Launcher], None]:
        """Get pre-launch callback."""

        def callback(launcher: Launcher) -> None:
            """Perform additional pre-launch activities (callback).

            This is invoked by launcher::_pre_launch().
            """

        return callback

    def post_finish(self) -> Callable[[str], None]:
        """Get post finish callback."""

        def callback(status: str) -> None:
            """Perform additional post-finish activities (callback).

            This is invoked by launcher::_post_finish().
            """

        return callback

    def get_timeout_mins(self) -> float | None:
        """Return the timeout in minutes."""


class CompileSim(Deploy):
    """Abstraction for building the simulation executable."""

    target = "build"
    cmds_list_vars: ClassVar = ["pre_build_cmds", "post_build_cmds"]
    weight = 5

    def __init__(self, build_mode, sim_cfg) -> None:
        """Initialise a Sim compile stage job deployment."""
        self.build_mode_obj = build_mode
        self.seed = sim_cfg.build_seed
        super().__init__(sim_cfg)

        # Needs to be after the wildcard expansion to log anything meaningful
        if self.build_timeout_mins:
            log.debug(
                'Timeout for job "%s" is %d minutes.',
                self.name,
                self.build_timeout_mins,
            )

    @staticmethod
    def new(build_mode_obj: "BuildMode", sim_cfg: "SimCfg") -> "CompileSim":
        """Create a new CompileSim object.

        Args:
            build_mode_obj: build mode instance
            sim_cfg: Simulation config object

        Returns:
            new CompileSim object.

        """
        return CompileSim(build_mode=build_mode_obj, sim_cfg=sim_cfg)

    def _define_attrs(self) -> None:
        """Define attributes."""
        super()._define_attrs()
        self.mandatory_cmd_attrs.update(
            {
                # tool srcs
                "proj_root": False,
                # Flist gen
                "sv_flist_gen_cmd": False,
                "sv_flist_gen_dir": False,
                "sv_flist_gen_opts": False,
                # Build
                "pre_build_cmds": False,
                "build_cmd": False,
                "build_dir": False,
                "build_opts": False,
                "post_build_cmds": False,
            },
        )

        self.mandatory_misc_attrs.update(
            {
                "build_fail_patterns": False,
                "build_pass_patterns": False,
                "build_timeout_mins": False,
                "cov_db_dir": False,
            },
        )

    def _set_attrs(self) -> None:
        super()._extract_attrs(self.build_mode_obj.__dict__)
        super()._set_attrs()

        # Dont run the compile job in GUI mode.
        self.gui = False

        # 'build_mode' is used as a substitution variable in the HJson.
        self.build_mode = self.name
        self.job_name += f"_{self.build_mode}"
        if self.sim_cfg.cov:
            self.output_dirs += [self.cov_db_dir]
        self.pass_patterns = self.build_pass_patterns
        self.fail_patterns = self.build_fail_patterns

        if self.sim_cfg.args.build_timeout_mins is not None:
            self.build_timeout_mins = self.sim_cfg.args.build_timeout_mins

    def pre_launch(self) -> Callable[[Launcher], None]:
        """Get pre-launch callback."""

        def callback(_: Launcher) -> None:
            """Perform pre-launch tasks."""
            # Delete old coverage database directories before building again. We
            # need to do this because the build directory is not 'renewed'.
            rm_path(self.cov_db_dir)

        return callback

    def get_timeout_mins(self) -> float:
        """Return the timeout in minutes.

        Limit build jobs to 60 minutes if the timeout is not set.
        """
        return self.build_timeout_mins if self.build_timeout_mins is not None else 60


class CompileOneShot(Deploy):
    """Abstraction for building the design (used by non-DV flows)."""

    target = "build"

    def __init__(self, build_mode, sim_cfg) -> None:
        """Initialise a CompileOneShot object."""
        self.build_mode_obj = build_mode
        super().__init__(sim_cfg)

        # Needs to be after the wildcard expansion to log anything meaningful
        if self.build_timeout_mins:
            log.debug(
                'Timeout for job "%s" is %d minutes.',
                self.name,
                self.build_timeout_mins,
            )

    def _define_attrs(self) -> None:
        super()._define_attrs()
        self.mandatory_cmd_attrs.update(
            {
                # tool srcs
                "proj_root": False,
                # Flist gen
                "sv_flist_gen_cmd": False,
                "sv_flist_gen_dir": False,
                "sv_flist_gen_opts": False,
                # Build
                "build_dir": False,
                "build_cmd": False,
                "build_opts": False,
                "build_log": False,
                "build_timeout_mins": False,
                "post_build_cmds": False,
                "pre_build_cmds": False,
                # Report processing
                "report_cmd": False,
                "report_opts": False,
            },
        )

        self.mandatory_misc_attrs.update(
            {"build_fail_patterns": False, "build_pass_patterns": False},
        )

    def _set_attrs(self) -> None:
        super()._extract_attrs(self.build_mode_obj.__dict__)
        super()._set_attrs()

        # 'build_mode' is used as a substitution variable in the HJson.
        self.build_mode = self.name
        self.job_name += f"_{self.build_mode}"
        self.fail_patterns = self.build_fail_patterns
        self.pass_patterns = self.build_pass_patterns

        if self.sim_cfg.args.build_timeout_mins is not None:
            self.build_timeout_mins = self.sim_cfg.args.build_timeout_mins

    def get_timeout_mins(self) -> float:
        """Return the timeout in minutes.

        Limit build jobs to 60 minutes if the timeout is not set.
        """
        return self.build_timeout_mins if self.build_timeout_mins is not None else 60


class RunTest(Deploy):
    """Abstraction for running tests. This is one per seed for each test."""

    # Initial seed values when running tests (if available).
    target = "run"
    seeds = []
    fixed_seed = None
    cmds_list_vars = ["pre_run_cmds", "post_run_cmds"]

    def __init__(self, index, test, build_job, sim_cfg: "SimCfg") -> None:
        self.test_obj = test
        self.index = index
        self.build_seed = sim_cfg.build_seed
        self.seed = RunTest.get_seed()
        # Systemverilog accepts seeds with a maximum size of 32 bits.
        self.svseed = int(self.seed) & 0xFFFFFFFF
        self.simulated_time = JobTime()
        super().__init__(sim_cfg)

        # Needs to be after the wildcard expansion to log anything meaningful
        if self.run_timeout_mins:
            log.debug(
                'Timeout for job "%s" is %d minutes.',
                self.full_name,
                self.run_timeout_mins,
            )

        if build_job is not None:
            self.dependencies.append(build_job)

        # We did something wrong if build_mode is not the same as the build_job
        # arg's name.
        assert self.build_mode == build_job.name

    def _define_attrs(self) -> None:
        super()._define_attrs()
        self.mandatory_cmd_attrs.update(
            {
                # tool srcs
                "proj_root": False,
                "uvm_test": False,
                "uvm_test_seq": False,
                "sw_images": False,
                "sw_build_device": False,
                "sw_build_cmd": False,
                "sw_build_opts": False,
                "run_dir": False,
                "pre_run_cmds": False,
                "run_cmd": False,
                "run_opts": False,
                "post_run_cmds": False,
                "build_seed": True,  # Already set in the constructor.
                "seed": True,  # Already set in the constructor.
            },
        )

        self.mandatory_misc_attrs.update(
            {
                "cov_db_dir": False,
                "cov_db_test_dir": False,
                "run_dir_name": False,
                "run_fail_patterns": False,
                "run_pass_patterns": False,
                "run_timeout_mins": False,
                "run_timeout_multiplier": False,
            },
        )

    def _set_attrs(self) -> None:
        super()._extract_attrs(self.test_obj.__dict__)
        super()._set_attrs()

        # 'test' is used as a substitution variable in the HJson.
        self.test = self.name
        self.build_mode = self.test_obj.build_mode.name
        self.qual_name = self.run_dir_name + "." + str(self.seed)
        self.full_name = f"{self.sim_cfg.name}{self._variant_suffix}:{self.qual_name}"
        self.job_name += f"_{self.build_mode}"
        if self.sim_cfg.cov:
            self.output_dirs += [self.cov_db_dir]

        # In GUI mode, the log file is not updated; hence, nothing to check.
        if not self.gui:
            self.pass_patterns = self.run_pass_patterns
            self.fail_patterns = self.run_fail_patterns

        if self.sim_cfg.args.run_timeout_mins is not None:
            self.run_timeout_mins = self.sim_cfg.args.run_timeout_mins

        if self.sim_cfg.args.run_timeout_multiplier is not None:
            self.run_timeout_multiplier = self.sim_cfg.args.run_timeout_multiplier

        if self.run_timeout_mins and self.run_timeout_multiplier:
            self.run_timeout_mins = int(self.run_timeout_mins * self.run_timeout_multiplier)

        if self.run_timeout_multiplier:
            log.debug(
                'Timeout multiplier for job "%s" is %f.',
                self.full_name,
                self.run_timeout_multiplier,
            )

    def pre_launch(self) -> Callable[[Launcher], None]:
        """Perform pre-launch tasks."""

        def callback(launcher: Launcher) -> None:
            """Perform pre-launch tasks."""
            launcher.renew_odir = True

        return callback

    def post_finish(self) -> Callable[[str], None]:
        """Get post finish callback."""

        def callback(status: str) -> None:
            """Perform tidy up tasks."""
            if status != "P":
                # Delete the coverage data if available.
                rm_path(self.cov_db_test_dir)

        return callback

    @staticmethod
    def get_seed() -> int:
        """Get the test random seed."""
        # If --seeds option is passed, then those custom seeds are consumed
        # first. If --fixed-seed <val> is also passed, the subsequent tests
        # (once the custom seeds are consumed) will be run with the fixed seed.
        if not RunTest.seeds:
            if RunTest.fixed_seed is not None:
                return RunTest.fixed_seed
            for _i in range(1000):
                seed = random.getrandbits(256)
                RunTest.seeds.append(seed)
        return RunTest.seeds.pop(0)

    def get_timeout_mins(self):
        """Return the timeout in minutes.

        Limit run jobs to 60 minutes if the timeout is not set.
        """
        return self.run_timeout_mins if self.run_timeout_mins is not None else 60


class CovUnr(Deploy):
    """Abstraction for coverage UNR flow."""

    target = "cov_unr"

    def __init__(self, sim_cfg) -> None:
        """Initialise a UNR coverage calculation job deployment."""
        super().__init__(sim_cfg)

    def _define_attrs(self) -> None:
        super()._define_attrs()
        self.mandatory_cmd_attrs.update(
            {
                # tool srcs
                "proj_root": False,
                # Need to generate filelist based on build mode
                "sv_flist_gen_cmd": False,
                "sv_flist_gen_dir": False,
                "sv_flist_gen_opts": False,
                "build_dir": False,
                "cov_unr_build_cmd": False,
                "cov_unr_build_opts": False,
                "cov_unr_run_cmd": False,
                "cov_unr_run_opts": False,
            },
        )

        self.mandatory_misc_attrs.update(
            {
                "cov_unr_dir": False,
                "cov_merge_db_dir": False,
                "build_fail_patterns": False,
            },
        )

    def _set_attrs(self) -> None:
        super()._set_attrs()
        self.qual_name = self.target
        self.full_name = f"{self.sim_cfg.name}{self._variant_suffix}:{self.qual_name}"
        self.input_dirs += [self.cov_merge_db_dir]

        # Reuse the build_fail_patterns set in the HJson.
        self.fail_patterns = self.build_fail_patterns


class CovMerge(Deploy):
    """Abstraction for merging coverage databases."""

    target = "cov_merge"
    weight = 10

    def __init__(self, run_items, sim_cfg) -> None:
        """Initialise a job deployment to merge coverage databases."""
        # Construct the cov_db_dirs right away from the run_items. This is a
        # special variable used in the HJson. The coverage associated with
        # the primary build mode needs to be first in the list.
        self.cov_db_dirs = []
        for run in run_items:
            if run.cov_db_dir not in self.cov_db_dirs:
                if sim_cfg.primary_build_mode == run.build_mode:
                    self.cov_db_dirs.insert(0, run.cov_db_dir)
                else:
                    self.cov_db_dirs.append(run.cov_db_dir)

        # Sort the cov_db_dir except for the first directory
        if len(self.cov_db_dirs) > 1:
            self.cov_db_dirs = [self.cov_db_dirs[0], *sorted(self.cov_db_dirs[1:])]

        # Early lookup the cov_merge_db_dir, which is a mandatory misc
        # attribute anyway. We need it to compute additional cov db dirs.
        self.cov_merge_db_dir = subst_wildcards("{cov_merge_db_dir}", sim_cfg.__dict__)

        # Prune previous merged cov directories, keeping past 7 dbs.
        prev_cov_db_dirs = clean_odirs(odir=self.cov_merge_db_dir, max_odirs=7)

        # If the --cov-merge-previous command line switch is passed, then
        # merge coverage with the previous runs.
        if sim_cfg.cov_merge_previous:
            self.cov_db_dirs += [str(item) for item in prev_cov_db_dirs]

        super().__init__(sim_cfg)
        self.dependencies += run_items
        # Run coverage merge even if one test passes.
        self.needs_all_dependencies_passing = False

        # Append cov_db_dirs to the list of exports.
        self.exports["cov_db_dirs"] = shlex.quote(" ".join(self.cov_db_dirs))

    def _define_attrs(self) -> None:
        super()._define_attrs()
        self.mandatory_cmd_attrs.update({"cov_merge_cmd": False, "cov_merge_opts": False})

        self.mandatory_misc_attrs.update({"cov_merge_dir": False, "cov_merge_db_dir": False})

    def _set_attrs(self) -> None:
        super()._set_attrs()
        self.qual_name = self.target
        self.full_name = f"{self.sim_cfg.name}{self._variant_suffix}:{self.qual_name}"

        # For merging coverage db, the precise output dir is set in the HJson.
        self.odir = self.cov_merge_db_dir
        self.input_dirs += self.cov_db_dirs
        self.output_dirs = [self.odir]


class CovReport(Deploy):
    """Abstraction for coverage report generation."""

    target = "cov_report"
    weight = 10

    def __init__(self, merge_job, sim_cfg) -> None:
        """Initialise a job deployment to generate a coverage report."""
        super().__init__(sim_cfg)
        self.dependencies.append(merge_job)

    def _define_attrs(self) -> None:
        super()._define_attrs()
        self.mandatory_cmd_attrs.update({"cov_report_cmd": False, "cov_report_opts": False})

        self.mandatory_misc_attrs.update(
            {
                "cov_report_dir": False,
                "cov_merge_db_dir": False,
                "cov_report_txt": False,
            },
        )

    def _set_attrs(self) -> None:
        super()._set_attrs()
        self.qual_name = self.target
        self.full_name = f"{self.sim_cfg.name}{self._variant_suffix}:{self.qual_name}"

        # Keep track of coverage results, once the job is finished.
        self.cov_total = ""
        self.cov_results = ""
        self.cov_results_dict = {}

    def post_finish(self) -> Callable[[str], None]:
        """Get post finish callback."""

        def callback(status: str) -> None:
            """Extract the coverage results summary for the dashboard.

            If the extraction fails, an appropriate exception is raised, which must
            be caught by the caller to mark the job as a failure.
            """
            if self.dry_run or status != "P":
                return

            plugin = get_sim_tool_plugin(tool=self.sim_cfg.tool)

            results, self.cov_total = plugin.get_cov_summary_table(
                cov_report_path=self.cov_report_txt,
            )

            colalign = ("center",) * len(results[0])
            self.cov_results = tabulate(
                results, headers="firstrow", tablefmt="pipe", colalign=colalign
            )
            for tup in zip(*results, strict=False):
                self.cov_results_dict[tup[0]] = tup[1]

        return callback


class CovAnalyze(Deploy):
    """Abstraction for running the coverage analysis tool."""

    target = "cov_analyze"

    def __init__(self, sim_cfg) -> None:
        """Initialise a job deployment for running coverage analysis."""
        # Enforce GUI mode for coverage analysis.
        sim_cfg.gui = True
        super().__init__(sim_cfg)

    def _define_attrs(self) -> None:
        super()._define_attrs()
        self.mandatory_cmd_attrs.update(
            {
                # tool srcs
                "proj_root": False,
                "cov_analyze_cmd": False,
                "cov_analyze_opts": False,
            },
        )

        self.mandatory_misc_attrs.update({"cov_analyze_dir": False, "cov_merge_db_dir": False})

    def _set_attrs(self) -> None:
        super()._set_attrs()
        self.qual_name = self.target
        self.full_name = f"{self.sim_cfg.name}{self._variant_suffix}:{self.qual_name}"
        self.input_dirs += [self.cov_merge_db_dir]
