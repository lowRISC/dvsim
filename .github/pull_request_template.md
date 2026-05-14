<!--
CONTRIBUTION GUIDELINES
=======================

For a full reference, refer to the following documents:
- CONTRIBUTING.md
- CLA

COMMIT FORMAT
=============
Each commit merged from this PR drives an automatic release. Choose the right
type — it directly determines the version bump on the next release.

  TYPE        SEMVER IMPACT    USE WHEN...
  ─────────────────────────────────────────────────────────────────────────────
  feat        minor bump       adding new user-facing behaviour or CLI options
  fix         patch bump       correcting a bug in existing behaviour
  perf        patch bump       improving performance without changing behaviour
  refactor    patch bump       restructuring code without changing behaviour
  docs        no release       documentation-only changes
  test        no release       adding or fixing tests
  ci          no release       CI workflow changes
  chore       no release       maintenance (deps, tooling, config)
  build       no release       build system changes
  revert      patch bump       reverting a previous commit

BREAKING CHANGES → major bump
  Append ! to the type:  feat!: remove --legacy-flag
  Or add a footer:       BREAKING CHANGE: <description>

FORMAT
  <type>[(<scope>)][!]: <short description>   ← 100 chars max
  <blank line>
  <optional body>
  <blank line>
  Signed-off-by: Name <email>                 ← required; use git commit -s

EXAMPLES
  feat(scheduler): add --max-jobs CLI flag
  fix: handle empty testplan gracefully
  feat!: remove Python 3.9 support
  refactor(sim): extract tool selection into factory

For further info about the release processes, refer to the the following documents:
- doc/releasing.md
-->

## Description

<!-- Describe what this PR does and why. -->

## Checklist

- [ ] All commits are signed off (`git commit -s`), indicating acceptance of the CLA
- [ ] Commit messages follow the conventional commit format (`<type>[(<scope>)][!]: <description>`)
  - [ ] The commit type correctly reflects the semver impact of the change
  - [ ] Breaking changes are marked with `!` or a `BREAKING CHANGE:` footer
- [ ] New behaviour is covered by tests
