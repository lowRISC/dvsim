#!/usr/bin/env python3
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import re
import sys

from git import Repo

logger = logging.getLogger(__name__)

# Maximum length of the summary line in the commit message (the first line)
# There is no hard limit, but a typical convention is to keep this line at or
# below 50 characters, with occasional outliers.
COMMIT_MSG_MAX_SUMMARY_LEN = 100


def error(msg: str, commit: str | None = None) -> None:
    """Log error."""
    full_msg = f"Commit {commit.hexsha}: {msg}" if commit else msg
    logger.error(full_msg)


def warning(msg: str, commit: str | None = None) -> None:
    """Log warning."""
    full_msg = f"Commit {commit.hexsha}: {msg}" if commit else msg
    logger.warning(full_msg)


def lint_commit_author(commit: str) -> bool:
    """Check commit author."""
    success = True
    if commit.author.email.endswith("users.noreply.github.com"):
        error(
            f"Commit author has no valid email address set: "  # noqa: F541
            "{commit.author.email!r}. "
            'Use "git config user.email user@example.com" to '
            "set a valid email address, then update the commit "
            'with "git rebase -i" and/or '
            '"git commit --amend --signoff --reset-author". '
            "Also check your GitHub settings at "
            "https://github.com/settings/emails: your email address "
            'must be verified, and the option "Keep my email address '
            'private" must be disabled. '
            "This command will also sign off your commit indicating agreement "
            "to the Contributor License Agreement. See CONTRIBUTING.md for "
            "more details.",
            commit,
        )
        success = False

    if " " not in commit.author.name:
        warning(
            f"The commit author name {commit.author.name!r} contains no space. "
            "Use \"git config user.name 'Johnny English'\" to "
            'set your real name, and update the commit with "git rebase -i " '
            'and/or "git commit --amend --signoff --reset-author". '
            "This command will also sign off your commit indicating agreement "
            "to the Contributor License Agreement. See CONTRIBUTING.md for "
            "more details.",
            commit,
        )
        # A warning doesn't fail lint.

    return success


def lint_commit_message(commit: str) -> bool:
    """Check commit message."""
    success = True
    lines = commit.message.splitlines()

    # Check length of summary line.
    summary_line_len = len(lines[0])
    if summary_line_len > COMMIT_MSG_MAX_SUMMARY_LEN:
        error(
            f"The summary line in the commit message is {summary_line_len} "
            f"characters long; only {COMMIT_MSG_MAX_SUMMARY_LEN} characters "
            "are allowed.",
            commit,
        )
        success = False

    # Check for an empty line separating the summary line from the long
    # description.
    if len(lines) > 1 and lines[1] != "":
        error(
            "The second line of a commit message must be empty, as it "
            "separates the summary from the long description.",
            commit,
        )
        success = False

    # Check that the commit message contains at least one Signed-off-by line
    # that matches the author name and email. There might be other signoffs (if
    # there are multiple authors). We don't have any requirements about those
    # at the moment and just pass them through.
    signoff_lines = []
    signoff_pfx = "Signed-off-by: "
    for line in lines:
        if not line.startswith(signoff_pfx):
            continue

        signoff_body = line[len(signoff_pfx) :]
        match = re.match(r"[^<]+ <[^>]*>$", signoff_body)
        if match is None:
            error(
                f"Commit has Signed-off-by line {line!r}, but the second part "
                "is not of the required form. It should be of the form "
                '"Signed-off-by: NAME <EMAIL>".'
            )
            success = False

        signoff_lines.append(line)

    expected_signoff_line = f"Signed-off-by: {commit.author.name} <{commit.author.email}>"
    signoff_req_msg = (
        "The commit message must contain a Signed-off-by line "
        "that matches the commit author name and email, "
        "indicating agreement to the Contributor License "
        "Agreement. See CONTRIBUTING.md for more details. "
        'You can use "git commit --signoff" to ask git to add '
        "this line for you."
    )

    if not signoff_lines:
        error(f"Commit has no Signed-off-by line. {signoff_req_msg}")
        success = False

    elif expected_signoff_line not in signoff_lines:
        error(
            (
                "Commit has one or more Signed-off-by lines, but not the one "
                f'we expect. We expected to find "{expected_signoff_line}". '
            )
            + signoff_req_msg
        )
        success = False

    return success


def lint_commit(commit: str) -> bool:
    """Check a commit."""
    return all(
        [
            lint_commit_author(commit),
            lint_commit_message(commit),
        ]
    )


def main() -> None:
    """Commit message lint check."""
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Check commit metadata for common mistakes",
    )
    parser.add_argument(
        "commit_range",
        metavar="commit-range",
        help="commit range to check (must be understood by git log)",
    )
    args = parser.parse_args()

    commit_range = f"{args.commit_range}..HEAD"
    logger.info("Checking commit range %s", commit_range)

    lint_successful = True

    for commit in Repo().iter_commits(commit_range):
        logger.info("Checking commit %s", commit.hexsha)

        if len(commit.parents) > 1:
            logger.info("Skipping merge commit.")
            continue

        if not lint_commit(commit):
            lint_successful = False

    if not lint_successful:
        error("Commit lint failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
