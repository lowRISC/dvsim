#!/usr/bin/env python3
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Check all files for license header."""

import subprocess
import sys
from pathlib import Path

from logzero import logger

LICENSE = (
    "Copyright lowRISC contributors (OpenTitan project).",
    "Licensed under the Apache License, Version 2.0, see LICENSE for details.",
    "SPDX-License-Identifier: Apache-2.0",
)

IGNORE_NAMES = [
    "CLA",
    "LICENSE",
    "NOTICE",
    ".python-version",
    "CHANGELOG.md",
]

IGNORE_SUFFIXES = [".lock"]

OPTIONAL_TRAILING_NEWLINE = [".nix", ".md"]


def check_header(*, text: str, trailing_newline_optional: bool = False) -> bool:
    """Check header complies with license requirmeents."""
    lines = text.splitlines()

    try:
        for i in range(2):
            if all(
                [
                    LICENSE[0] in lines[i],
                    LICENSE[1] in lines[i + 1],
                    LICENSE[2] in lines[i + 2],
                    trailing_newline_optional or lines[i + 3] == "",
                ]
            ):
                return True

    except IndexError:
        pass

    return False


p = subprocess.run(
    ["git", "ls-tree", "--full-tree", "-r", "--name-only", "HEAD"],
    capture_output=True,
    check=True,
)

failed = []
for f in p.stdout.decode(encoding="utf8").splitlines():
    # ignore empty lines
    if not f:
        continue

    path = Path(f)

    if path.name in IGNORE_NAMES or "".join(path.suffixes) in IGNORE_SUFFIXES:
        logger.info("Skipping ignored file: %s", path)
        continue

    # Ignore binary files
    try:
        text = path.read_text()

    except UnicodeDecodeError:
        logger.info("Skipping binary file: %s", path)
        continue

    logger.debug("Checking: %s", path)

    if not check_header(
        text=text,
        trailing_newline_optional=path.suffix in OPTIONAL_TRAILING_NEWLINE,
    ):
        failed.append(path)

for path in failed:
    logger.error(f"failed: {path}")

sys.exit(min(len(failed), 255))
