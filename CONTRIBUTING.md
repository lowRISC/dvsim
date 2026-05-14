<!--
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
-->
# Contributing to DVSim

## Contributor License Agreement

Contributions must be accompanied by a sign-off indicating acceptance of the
Contributor License Agreement (see [CLA](CLA) for full text). The sign-off is
added once per commit in the commit message footer, and can be inserted
automatically with:

```
git commit -s
```

This produces a line of the form:

```
Signed-off-by: Random J Developer <random@developer.example.org>
```

By adding this sign-off you are certifying:

_I agree to be bound by the terms of the Contributor License Agreement located
at the root of the project repository, and I agree that this submission
constitutes a "Contribution" under that Agreement._

Note that this project and any contributions to it are public. A record of all
contributions (including any personal information submitted with it) is
maintained indefinitely and may be redistributed consistent with this project
or the open source license(s) involved.

## Commit messages

DVSim uses [Conventional Commits](https://www.conventionalcommits.org/) to
drive automatic semantic versioning. Every commit that lands on `master` is
parsed by `python-semantic-release` and the commit type determines the version
bump in the next release. **Choosing the right type is important.**

The summary line must be 100 characters or fewer.
See [docs/releasing.md](doc/releasing.md) for the full type list and their semver
impact.

## Pull requests

- Changes must go through a pull request with at least one review before merge.
- Keep a clean commit history: no merge commits, no long chains of fixup patches.
  Use `git rebase -i` to squash or reorder before requesting review.
- Create pull requests from a fork rather than from branches in the upstream
  repository.
- If a relevant bug or tracking issue exists, reference it in the PR description
  and in the commit message body.
- Do not report security vulnerabilities through public GitHub issues or pull
  requests. See [SECURITY.md](SECURITY.md) for the responsible disclosure process.
- Do not include code under a non-Apache license without prior discussion.
