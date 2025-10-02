# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""rclone helper functions."""

import json
import os
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path

from logzero import logger

__all__ = (
    "check_rclone_installed",
    "rclone_copy",
    "rclone_list_dirs",
)


def check_rclone_installed() -> None:
    """Check rclone is installed."""
    try:
        proc = subprocess.run(
            ["rclone", "--version"],
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        logger.debug(proc.stdout.strip())

    except Exception:
        logger.exception("rclone is not installed - please install it first")
        raise


def rclone_copy(
    *,
    src_path: Path | str,
    dest_path: Path | str,
    extra_env: Mapping | None = None,
) -> None:
    """Clone dir to remote.

    Use the extra_env arg to configure RCLONE via environment variables
    [rclone config](https://rclone.org/docs/#config-file). For example,
    RCLONE_CONFIG_<remote>_<parameter>, where <remote> is the name of a remote
    location that can be used in a src/dest path string.

    Args:
        src_path: path to the source files as either a Path or any string that
            rclone will accept as a source.
        dest_path: path to the destination location as either a Path or any
            string that rclone will accept as a source.
        extra_env: mapping of extra environment variable key/value pairs for
            rclone, which can be used to configure rclone.

    """
    proc = subprocess.run(
        [
            "rclone",
            "copy",
            str(src_path),
            str(dest_path),
        ],
        env=os.environ | (extra_env or {}),
        capture_output=True,
        check=False,
    )
    output = proc.stdout.decode("utf-8")
    error = proc.stderr.decode("utf-8")

    if output:
        logger.debug("rclone: %s", output)

    if proc.returncode:
        logger.error(
            "rclone failed to copy from '%s' to '%s'",
            src_path,
            dest_path,
        )

        if error:
            logger.error(error)

        raise RuntimeError


def rclone_list_dirs(
    *,
    path: Path | str,
    extra_env: Mapping | None = None,
) -> Iterable[str]:
    """List the directories in the given path.

    Use the extra_env arg to configure RCLONE via environment variables
    [rclone config](https://rclone.org/docs/#config-file). For example,
    RCLONE_CONFIG_<remote>_<parameter>, where <remote> is the name of a remote
    location that can be used in a src/dest path string.

    Args:
        path: path to the directory to list
        extra_env: mapping of extra environment variable key/value pairs for
            rclone, which can be used to configure rclone.

    Returns:
        Iterable of directory names as strings

    """
    proc = subprocess.run(
        ["rclone", "lsjson", str(path), "--dirs-only"],
        env=os.environ | (extra_env or {}),
        capture_output=True,
        check=False,
    )

    if proc.returncode:
        err = proc.stderr.decode("utf-8")
        logger.error("rclone list dir failed: '%s'", path)
        logger.error(err)

        raise RuntimeError

    return [dir_info["Path"] for dir_info in json.loads(proc.stdout.decode("utf-8"))]
