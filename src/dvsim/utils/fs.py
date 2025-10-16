# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""file system utilities."""

import os
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from dvsim.logging import log

__all__ = (
    "TS_FORMAT",
    "TS_FORMAT_LONG",
    "mk_path",
    "mk_symlink",
    "rm_path",
)

# Timestamp format when creating directory backups.
TS_FORMAT = "%Y%m%d_%H%M%S"

# Timestamp format when generating reports.
TS_FORMAT_LONG = "%A %B %d %Y %H:%M:%S UTC"


def rm_path(path: Path, *, ignore_error: bool = False) -> None:
    """Remove the specified path if it exists.

    'path' is a Path-like object. If it does not exist, the function simply
    returns. If 'ignore_error' is set, then exception caught by the remove
    operation is raised, else it is ignored.
    """
    # interface claims to be Path-like, but to be sure not to to introduce
    # regressions convert to Path anyway.
    path = Path(path)

    # Nothing to do
    if not path.exists():
        return

    if path.is_file() or path.is_symlink():
        path.unlink()
        return

    try:
        shutil.rmtree(path)

    except OSError:
        log.exception("Failed to remove %s:\n", path)

        if not ignore_error:
            raise


def mk_path(path: Path) -> None:
    """Create the specified path if it does not exist.

    'path' is a Path-like object. If it does exist, the function simply
    returns. If it does not exist, the function creates the path and its
    parent dictories if necessary.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)

    except PermissionError:
        log.exception("Failed to create directory %s", path)
        sys.exit(1)


def mk_symlink(*, path: Path, link: Path) -> None:
    """Create a symlink from the given path.

    'link' is a Path-like object. If it does exist, remove the existing link
    and create a new symlink with this given path.
    If it does not exist, the function creates the symlink with the given path.
    """
    if link.exists():
        if not link.is_symlink():
            log.error(
                "Trying to create symlink %s, existing non symlink file found",
                link,
            )
            raise TypeError

        link.unlink()

    link.symlink_to(path)


def clean_odirs(
    odir: Path,
    max_odirs: int,
    ts_format: str = TS_FORMAT,
) -> Sequence[Path | str]:
    """Clean previous output directories.

    When running jobs, we may want to maintain a limited history of
    previous invocations. This method finds and deletes the output
    directories at the base of input arg 'odir' with the oldest timestamps,
    if that limit is reached. It returns a list of directories that
    remain after deletion.
    """
    odir = Path(odir)

    if odir.exists():
        # If output directory exists, back it up.
        ts = datetime.fromtimestamp(os.stat(odir).st_ctime).strftime(ts_format)
        # Prior to Python 3.9, shutil may run into an error when passing in
        # Path objects (see https://bugs.python.org/issue32689). While this
        # has been fixed in Python 3.9, string casts are added so that this
        # also works with older versions.
        shutil.move(str(odir), str(odir.with_name(ts)))

    # Get list of past output directories sorted by creation time.
    pdir = odir.resolve().parent
    if not pdir.exists():
        return []

    dirs = sorted(
        [old for old in pdir.iterdir() if (old.is_dir() and old != "summary")],
        key=os.path.getctime,
        reverse=True,
    )

    for old in dirs[max(0, max_odirs - 1) :]:
        shutil.rmtree(old, ignore_errors=True)

    return [] if max_odirs == 0 else dirs[: max_odirs - 1]
