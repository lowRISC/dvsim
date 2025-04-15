# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""DVSim project."""

import os
import shlex
import subprocess
import sys
from argparse import Namespace
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from dvsim.config.load import load_cfg
from dvsim.logging import log
from dvsim.utils import (
    rm_path,
    run_cmd_with_timeout,
)

__all__ = ("Project",)


class FlowConfig(BaseModel):
    """Flow configuration data."""

    model_config = ConfigDict(frozen=True, extra="allow")


class Project(BaseModel):
    """Project meta data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    top_cfg_path: Path
    root_path: Path
    src_path: Path
    scratch_path: Path
    branch: str
    job_prefix: str

    logfile: Path
    run_dir: Path

    def save(self) -> None:
        """Save project meta to file."""
        meta_json = self.model_dump_json(indent=2)

        log.debug("Project meta:\n%s", meta_json)

        self.run_dir.mkdir(parents=True, exist_ok=True)

        (self.run_dir / "project.json").write_text(meta_json)

    def load_config(
        self,
        select_cfgs: Sequence[str] | None,
        args: Namespace,
    ) -> Mapping:
        """Load the project configuration.

        Args:
            project_cfg: metadata about the project
            select_cfgs: list of child config names to use from the primary config
            args: are the arguments passed to the CLI

        Returns:
            Project configuration.

        """
        log.info("Loading primary config file: %s", self.top_cfg_path)

        # load the whole project config data
        cfg = dict(
            load_cfg(
                path=self.top_cfg_path,
                path_resolution_wildcards={
                    "proj_root": self.root_path,
                },
                select_cfgs=select_cfgs,
            ),
        )

        # Tool specified on CLI overrides the file based config
        if args.tool is not None:
            cfg["tool"] = args.tool

        return cfg

    @staticmethod
    def load(path: Path) -> "Project":
        """Load project meta from file."""
        data = (path / "project.json").read_text()
        return Project.model_validate_json(data)

    @staticmethod
    def init(
        cfg_path: Path,
        proj_root: Path | None,
        scratch_root: Path | None,
        branch: str,
        *,
        job_prefix: str = "",
        purge: bool = False,
        dry_run: bool = False,
        remote: bool = False,
    ) -> "Project":
        """Initialise a project workspace.

        If --remote switch is set, a location in the scratch area is chosen as the
        new proj_root. The entire repo is copied over to this location. Else, the
        proj_root is discovered using get_proj_root() method, unless the user
        overrides it on the command line.

        This function returns the updated proj_root src and destination path. If
        --remote switch is not set, the destination path is identical to the src
        path. Likewise, if --dry-run is set.
        """
        if not cfg_path.exists():
            log.fatal("Path to config file %s appears to be invalid.", cfg_path)
            sys.exit(1)

        branch = _resolve_branch(branch)

        src_path = Path(proj_root) if proj_root else get_proj_root()

        scratch_path = resolve_scratch_root(
            scratch_root,
            src_path,
        )

        # Check if jobs are dispatched to external compute machines. If yes,
        # then the repo needs to be copied over to the scratch area
        # accessible to those machines.
        # If --purge arg is set, then purge the repo_top that was copied before.
        if remote and not dry_run:
            root_path = scratch_path / branch / "repo_top"
            if purge:
                rm_path(root_path)
            copy_repo(src_path, root_path)
        else:
            root_path = src_path

        log.info("[proj_root]: %s", root_path)

        # Create an empty FUSESOC_IGNORE file in scratch_root. This ensures that
        # any fusesoc invocation from a job won't search within scratch_root for
        # core files.
        (scratch_path / "FUSESOC_IGNORE").touch()

        cfg_path = cfg_path.resolve()
        if remote:
            cfg_path = root_path / cfg_path.relative_to(src_path)

        run_dir = scratch_path / branch
        return Project(
            top_cfg_path=cfg_path,
            root_path=root_path,
            src_path=src_path,
            scratch_path=scratch_path,
            branch=branch,
            job_prefix=job_prefix,
            logfile=run_dir / "run.log",
            run_dir=run_dir,
        )


def _network_dir_accessible_and_exists(
    path: Path,
    timeout: int = 1,
) -> bool:
    """Check network path is accessible and exists with timeout.

    Path could be mounted in a filesystem (such as NFS) on
    a network drive. If the network is down, it could cause the
    access access check to hang. So run a simple ls command with a
    timeout to prevent the hang.

    Args:
        path: the directory path to check
        timeout: number of seconds to wait before giving up

    Returns:
        True if the directory was listable otherwise False

    """
    (out, status) = run_cmd_with_timeout(
        cmd="ls -d " + str(path),
        timeout=timeout,
        exit_on_failure=False,
    )

    return status == 0 and out != ""


def _ensure_dir_exists_and_accessible(path: Path) -> None:
    """Directory exists and is accessible."""
    try:
        path.mkdir(exist_ok=True, parents=True)
    except PermissionError as e:
        log.fatal(
            f"Failed to create dir {path}:\n{e}.",
        )
        sys.exit(1)

    if not os.access(path, os.W_OK):
        log.fatal(f"Path {path} is not writable!")
        sys.exit(1)


def resolve_scratch_root(
    arg_scratch_root: Path | None,
    proj_root: Path,
) -> Path:
    """Resolve the scratch root directory.

    Among the available options:
        If set on the command line, then use that as a preference.
        Else, check if $SCRATCH_ROOT env variable exists and is a directory.
        Else use the default (<proj_root>/scratch)

    Try to create the directory if it does not already exist.
    """
    scratch_root_env = os.environ.get("SCRATCH_ROOT")

    if arg_scratch_root:
        scratch_root = Path(os.path.realpath(str(arg_scratch_root)))

    elif scratch_root_env:
        resolved_path = Path(os.path.realpath(scratch_root_env))

        if _network_dir_accessible_and_exists(resolved_path):
            scratch_root = resolved_path

        else:
            log.warning('Scratch root "%s" is not accessible', resolved_path)

            scratch_root = proj_root / "scratch"
    else:
        scratch_root = proj_root / "scratch"

    log.info('Using scratch root "%s"', scratch_root)

    _ensure_dir_exists_and_accessible(scratch_root)

    return scratch_root


def get_proj_root() -> Path:
    """Get the project root directory path.

    this is used to construct the full paths.
    """
    cmd = ["git", "rev-parse", "--show-toplevel"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
    )

    proj_root = result.stdout.decode("utf-8").strip()

    if not proj_root:
        cmd_line = " ".join(cmd)
        err_str = result.stderr.decode("utf-8")

        log.error(
            "Attempted to find the root of this GitHub repository by running:"
            "\n%s\nBut this command has failed:\n%s",
            cmd_line,
            err_str,
        )
        sys.exit(1)

    return Path(proj_root)


def copy_repo(src: Path, dest: Path) -> None:
    """Copy over the repo to a new location.

    The repo is copied over from src to dest area. It tentatively uses the
    rsync utility which provides the ability to specify a file containing some
    exclude patterns to skip certain things from being copied over. With GitHub
    repos, an existing `.gitignore` serves this purpose pretty well.
    """
    rsync_cmd = [
        "rsync",
        "--recursive",
        "--links",
        "--checksum",
        "--update",
        "--inplace",
        "--no-group",
    ]

    # Supply `.gitignore` from the src area to skip temp files.
    ignore_patterns_file = src / ".gitignore"
    if ignore_patterns_file.exists():
        # TODO: hack - include hw/foundry since it is excluded in .gitignore.
        rsync_cmd += [
            "--include=hw/foundry",
            f"--exclude-from={ignore_patterns_file}",
            "--exclude=.*",
        ]

    rsync_cmd += [str(src / "."), str(dest)]

    cmd = [
        "flock",
        "--timeout",
        "600",
        dest,
        "--command",
        " ".join([shlex.quote(w) for w in rsync_cmd]),
    ]

    log.info("[copy_repo] [dest]: %s", dest)
    log.verbose("[copy_repo] [cmd]: \n%s", " ".join(cmd))

    # Make sure the dest exists first.
    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        log.exception(
            "Failed to copy over %s to %s: %s",
            src,
            dest,
            e.stderr.decode("utf-8").strip(),
        )
    log.info("Done.")


def _resolve_branch(branch: str | None) -> str:
    """Choose a branch name for output files.

    If the --branch argument was passed on the command line, the branch
    argument is the branch name to use. Otherwise it is None and we use git to
    find the name of the current branch in the working directory.

    Note, as this name will be used to generate output files any forward
    slashes are replaced with single dashes to avoid being interpreted as
    directory hierarchy.
    """
    if branch is not None:
        return branch.replace("/", "-")

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        stdout=subprocess.PIPE,
        check=False,
    )
    branch = result.stdout.decode("utf-8").strip().replace("/", "-")
    if not branch:
        log.warning(
            'Failed to find current git branch. Setting it to "default"',
        )
        branch = "default"

    return branch
