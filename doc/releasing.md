<!--
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
-->

# Releasing DVSim

DVSim uses [python-semantic-release](https://python-semantic-release.readthedocs.io/)
to automate versioning and releases. Releases are created automatically when commits
land on `master` — there is no manual step to cut a release.

## How it works

1. A pull request is merged to `master`.
2. The `release` CI workflow runs `semantic-release version`, which inspects all
   commits since the previous release tag.
3. The highest-impact commit type in the changeset determines the version bump.
4. If any release-triggering commits are present, semantic-release:
   - Bumps the version in `pyproject.toml` and re-locks `uv.lock`
   - Updates `CHANGELOG.md`
   - Creates a signed release commit and a `vX.Y.Z` tag
   - Pushes the commit and tag to `master`
   - Creates a GitHub Release with source and distribution artifacts
   - Publishes the distribution to PyPI and TestPyPI

If no commit since the last release has a release-triggering type, no release is
created and the workflow exits cleanly.

## Commit types and semver impact

The commit type in each conventional commit message determines the version bump.
The highest-impact type across all commits since the last release wins.

| Type | Semver impact | Version example |
|---|---|---|
| Any type with `!` or `BREAKING CHANGE:` footer | **major** | `1.2.3` → `2.0.0` |
| `feat` | **minor** | `1.2.3` → `1.3.0` |
| `fix` | patch | `1.2.3` → `1.2.4` |
| `perf` | patch | `1.2.3` → `1.2.4` |
| `refactor` | patch | `1.2.3` → `1.2.4` |
| `docs` | none — no release | — |
| `test` | none — no release | — |
| `ci` | none — no release | — |
| `chore` | none — no release | — |
| `build` | none — no release | — |
| `style` | none — no release | — |
| `revert` | patch | `1.2.3` → `1.2.4` |

### Breaking changes

A **major** bump is triggered by either:

- Appending `!` to the type: `feat!: remove --legacy-flag`
- Adding a `BREAKING CHANGE:` footer to the commit body:

  ```
  feat: overhaul job configuration format

  BREAKING CHANGE: The `resources:` key in job HJSON configs is replaced
  by `compute:`. Existing configs must be updated.
  ```

### Squash commits

If a PR is squash-merged, the resulting single commit must itself carry a
valid conventional commit type. `parse_squash_commits = true` is set in
`pyproject.toml`, so semantic-release will also scan the squash commit body
for conventional commit lines from the original commits.

## Viewing the changelog

The [CHANGELOG.md](../CHANGELOG.md) at the repository root is updated
automatically by semantic-release on each release. It groups changes by type
and links to the commits and the GitHub diff for each release.

## Configuration

Semantic-release is configured in `pyproject.toml` under
`[tool.semantic_release]`. Key settings:

```toml
[tool.semantic_release]
commit_parser = "conventional"
version_toml = ["pyproject.toml:project.version"]

[tool.semantic_release.commit_parser_options]
minor_tags = ["feat"]
patch_tags = ["fix", "perf", "refactor"]
parse_squash_commits = true
ignore_merge_commits = true
```

The release workflow definition is in
[`.github/workflows/release.yml`](../.github/workflows/release.yml).
