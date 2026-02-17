# CHANGELOG

<!-- version list -->

## v1.9.1 (2026-02-17)

### Refactoring

- Add additional sim flow debug logs
  ([`36f9db4`](https://github.com/lowRISC/dvsim/commit/36f9db480bb51caf5100cb7c54c5d265af40f0cd))


## v1.9.0 (2026-02-16)

### Features

- Add DVSim version to generated reports
  ([`236dd45`](https://github.com/lowRISC/dvsim/commit/236dd457b3725a224ca2831c04e0e4d56646464c))


## v1.8.1 (2026-02-12)

### Bug Fixes

- Remove deadlocks by making the scheduler signal handler signal-safe
  ([`e9ed090`](https://github.com/lowRISC/dvsim/commit/e9ed090b375941911e9a605fc5428d15aec20bc5))

### Testing

- Mark scheduler signal tests as expected to pass
  ([`5400046`](https://github.com/lowRISC/dvsim/commit/54000465f12a983f78ad9e623906650df04edc23))


## v1.8.0 (2026-02-11)

### Build System

- Add `pytest-repeat` and `pytest-xdist` test development deps
  ([`54343fb`](https://github.com/lowRISC/dvsim/commit/54343fbadd862432104e457bcb5962e60447164a))

- Add `pytest-timeout` test dependency
  ([`4b2f0ad`](https://github.com/lowRISC/dvsim/commit/4b2f0ad1c3990f7f0b92a422cb60d81f82fec67f))

### Continuous Integration

- Make test runs strict
  ([`f9082e0`](https://github.com/lowRISC/dvsim/commit/f9082e08a10c0eb409f6444a31582df57fbf6991))

### Features

- Add scheduler Job/Launcher mocks
  ([`08f569e`](https://github.com/lowRISC/dvsim/commit/08f569ef07cd36e2d6db522b38f73d487f648a7f))

### Refactoring

- Make scheduler interactivity default to false
  ([`2b2d154`](https://github.com/lowRISC/dvsim/commit/2b2d1546b56032163da290fb834eef8b2856a147))

### Testing

- Add more scheduler tests
  ([`2a59a3a`](https://github.com/lowRISC/dvsim/commit/2a59a3af9a3ce9b3273e56555697073ae934a354))

- Add scheduler priority/weighting tests
  ([`332146a`](https://github.com/lowRISC/dvsim/commit/332146ae17714a7607f72b31b86d086ccb290974))

- Add scheduler signal handler tests
  ([`2fe396a`](https://github.com/lowRISC/dvsim/commit/2fe396a3d158b275c757564f8ecca9237df6427b))

- Add scheduler structural/dependency tests
  ([`dcb512a`](https://github.com/lowRISC/dvsim/commit/dcb512a29d8609fb6696dde9b0f275842bb93898))

- Add scheduler testing utilities & initial tests
  ([`a0aa678`](https://github.com/lowRISC/dvsim/commit/a0aa678d397db1f34ce1bb9155ce8a8f572ccd0e))

- Enable parallel pytest coverage
  ([`c9c0d38`](https://github.com/lowRISC/dvsim/commit/c9c0d38308960a63c9bcc8931cffeb3b5ec0cba4))


## v1.7.7 (2026-02-11)

### Bug Fixes

- `pyproject.toml` license spelling
  ([`ee24711`](https://github.com/lowRISC/dvsim/commit/ee247111393603658698df5117e8470d5714a584))

### Continuous Integration

- Pass CI dependency license check requirements
  ([`dd90bea`](https://github.com/lowRISC/dvsim/commit/dd90bea659bbf148b7a71842fcc99be27a154d9a))


## v1.7.6 (2026-02-09)

### Bug Fixes

- Replace 'E' local launcher poll status with a LauncherError
  ([`612011b`](https://github.com/lowRISC/dvsim/commit/612011bcd62d62addecb2918539b106bd7b3d5e3))

- Resolve JobSpec/str type error
  ([`e73575c`](https://github.com/lowRISC/dvsim/commit/e73575c460b14964377b26bb04d2460bc2cd8c9b))

### Refactoring

- Launcher poll always returns a status
  ([`4590ff8`](https://github.com/lowRISC/dvsim/commit/4590ff8d61a1234e7e5c8e28a67e366e47d406dc))

- Make Job Status an Enum
  ([`c75c923`](https://github.com/lowRISC/dvsim/commit/c75c9238e9c606073740ef527bf37c55471a18a6))

- Replace assert with RuntimeError
  ([`39ec250`](https://github.com/lowRISC/dvsim/commit/39ec250c3f43a169ecb1eabe09feb3af1f6fe81d))

- Resolve scheduler complexity lint warnings
  ([`8010a89`](https://github.com/lowRISC/dvsim/commit/8010a89f7d4d6baaf612b653d1499cae2758b1ae))


## v1.7.5 (2026-02-09)

### Bug Fixes

- Don't ignore input header message in EnlightenStatusPrinter
  ([`1a0f2dd`](https://github.com/lowRISC/dvsim/commit/1a0f2dd91e6274f3854684d07da0e63114f94938))

- Explicitly stop EnlightenStatusPrinter manager
  ([`cc9e703`](https://github.com/lowRISC/dvsim/commit/cc9e703b247fa44f0a2752529b52fd4a88e53e71))

- Handle EnlightenStatusPrinter early exit error
  ([`076b249`](https://github.com/lowRISC/dvsim/commit/076b2493b45641a1c27034644d0d8bc299a3bf81))


## v1.7.4 (2026-02-05)

### Bug Fixes

- Fix/add --version option to the CLIs
  ([`c2c7c78`](https://github.com/lowRISC/dvsim/commit/c2c7c7832c487b1269d2f4e2efe08f4cf6d0382f))


## v1.7.3 (2026-01-21)

### Bug Fixes

- Formal flow
  ([`bd28563`](https://github.com/lowRISC/dvsim/commit/bd2856360b8ca5355e860f7fb9c3d3888d4663e8))


## v1.7.2 (2026-01-21)

### Bug Fixes

- Hacky workaround for sim centric code
  ([`596d92f`](https://github.com/lowRISC/dvsim/commit/596d92fa4b0e69bf69b3b23e086db0ba72e3d0aa))

- Restore the lint flow old style report
  ([`85d8550`](https://github.com/lowRISC/dvsim/commit/85d8550db2fb4f3404ac6c96dc8baf64e8fd44bb))

### Refactoring

- Move sim related modules to top level package
  ([`9e31623`](https://github.com/lowRISC/dvsim/commit/9e31623a722e3ef4e500dc83072c49f5da803fd0))


## v1.7.1 (2026-01-08)

### Bug Fixes

- Render_static works pre python 3.13
  ([`5b68d0d`](https://github.com/lowRISC/dvsim/commit/5b68d0df34249e754c3328e45783ed96b33aad6b))

### Continuous Integration

- Prevent fail fast
  ([`e0958eb`](https://github.com/lowRISC/dvsim/commit/e0958eb8b659ca431646d6aae8e843e86f2a94f4))

### Testing

- Static content rendering
  ([`7989ba7`](https://github.com/lowRISC/dvsim/commit/7989ba75886fee4aecaa33e43e4fb8089405513a))


## v1.7.0 (2025-12-19)

### Features

- Block results report HTMX
  ([`e4522bd`](https://github.com/lowRISC/dvsim/commit/e4522bdca05b012c0d7f95c2583cc7e290f263ed))

- CORS
  ([`d6fc380`](https://github.com/lowRISC/dvsim/commit/d6fc3802d5a2ce7f13e26a9861df5d432c22156d))

- Create htmx wrapper for the summary page
  ([`7690af4`](https://github.com/lowRISC/dvsim/commit/7690af48f5727fdc8fe863670eb3c06ba46d37bc))

- Local copies of the js/css deps to enable sandboxed builds
  ([`dc18f96`](https://github.com/lowRISC/dvsim/commit/dc18f9671b3a2e58865ff697aac6b86b30672e30))

### Refactoring

- Create a higher level function to generate all reports
  ([`ca9cc18`](https://github.com/lowRISC/dvsim/commit/ca9cc188ca9f4098adcd4559adcaa71e4884e1d1))

- Report use the local css/js
  ([`182e9cb`](https://github.com/lowRISC/dvsim/commit/182e9cbfaf0857cf295c1e04cc616e33aa6a81be))


## v1.6.3 (2025-12-05)

### Bug Fixes

- Add failure buckets back into block report templates
  ([`b601833`](https://github.com/lowRISC/dvsim/commit/b6018333ea657c0ca52a01acc1ec8af9b518dc28))


## v1.6.2 (2025-12-04)

### Bug Fixes

- Add failure buckets data model back in
  ([`f89dc31`](https://github.com/lowRISC/dvsim/commit/f89dc31725453d242122b2dee48a8c3542ac8d52))


## v1.6.1 (2025-12-04)

### Bug Fixes

- Don't use python311 datetime alias
  ([`96b7c76`](https://github.com/lowRISC/dvsim/commit/96b7c765de2a025c62331683591d310d1ed8bf00))


## v1.6.0 (2025-11-25)

### Features

- Summary report more dashboard like
  ([`a784cb2`](https://github.com/lowRISC/dvsim/commit/a784cb2a2c2209799d08e5a41bd6fc99b01102e5))


## v1.5.0 (2025-11-21)

### Bug Fixes

- Use git commit directly from git
  ([`835926b`](https://github.com/lowRISC/dvsim/commit/835926b1b1155edd923245b826a6d7124ea43024))

### Features

- Add git utils for getting git commit hash
  ([`0cbdc49`](https://github.com/lowRISC/dvsim/commit/0cbdc496c5a9081759f999c2df98fab349e5741d))


## v1.4.0 (2025-11-21)

### Chores

- Nix flake update
  ([`8ed6cb3`](https://github.com/lowRISC/dvsim/commit/8ed6cb37e451596e51f319c9e67536348d73d9c7))

### Features

- Add report generation from JSON
  ([`69d8da6`](https://github.com/lowRISC/dvsim/commit/69d8da6cc65d71f8aceab3f00de1d6bbaf2f5598))

### Refactoring

- Move cli from module to package
  ([`865d28a`](https://github.com/lowRISC/dvsim/commit/865d28a00411fd46997abdd7f11a5addf46855ff))


## v1.3.1 (2025-11-21)

### Bug Fixes

- Restore variant to the report
  ([`87077a1`](https://github.com/lowRISC/dvsim/commit/87077a141f0d149141cefa0d7f3ae5ab8da4313f))

- Summary json link name
  ([`320b697`](https://github.com/lowRISC/dvsim/commit/320b69743fbd998a444c3497aec4ecc134b8347b))

- Upper case the block names to match the previous reports
  ([`8f2e2eb`](https://github.com/lowRISC/dvsim/commit/8f2e2eb3133fe5aeb0485ea733280e28666e000d))

### Refactoring

- Improve data models
  ([`c9317aa`](https://github.com/lowRISC/dvsim/commit/c9317aa8ad15bbc10cca4088f4c086fe7b909a83))


## v1.3.0 (2025-11-18)

### Features

- Add block report template
  ([`6e716fe`](https://github.com/lowRISC/dvsim/commit/6e716fea6f29c7a976d6f876fe6b6830827ae785))

- Add jinja2 template renderer
  ([`efeb68a`](https://github.com/lowRISC/dvsim/commit/efeb68add7b2b59e2b28cbbee0bdde04d648b5f0))

- Add report generation from templates
  ([`14406e4`](https://github.com/lowRISC/dvsim/commit/14406e40f059227bbdf00f6ee9134b23a612ca7f))

- Add summary report template
  ([`fa0852a`](https://github.com/lowRISC/dvsim/commit/fa0852aff97dd9e9a892c73f38b313e04e92a186))

- Redirect template
  ([`02b05fe`](https://github.com/lowRISC/dvsim/commit/02b05fe82ac0090f3b4a9cd708615150bfb62afd))

### Refactoring

- Clean up unused functions
  ([`40958fd`](https://github.com/lowRISC/dvsim/commit/40958fdbf325bd90eb75b27234759c6b6e003d0c))

- Tidy up results generation with direct model creation
  ([`75d91a3`](https://github.com/lowRISC/dvsim/commit/75d91a3cb37ff918c61f636748992265c29ffd68))


## v1.2.0 (2025-11-14)

### Features

- Add JSON summary generation
  ([`701cf04`](https://github.com/lowRISC/dvsim/commit/701cf048d2feca80e43b84b3b9c75b271bbdc0ea))

- Add ResultsSummary model
  ([`2c5b1e9`](https://github.com/lowRISC/dvsim/commit/2c5b1e95d73b01536ad802aa91d6ada819395513))


## v1.1.0 (2025-11-13)

### Features

- Add SimTool interface and implementations
  ([`b649826`](https://github.com/lowRISC/dvsim/commit/b64982650a104c69106e9d383144182b57b7bf15))

### Refactoring

- Use the tool plugins directly
  ([`b6416fa`](https://github.com/lowRISC/dvsim/commit/b6416fab1e88396d6f0244f4c77b7c780fba1043))

### Testing

- Add initial tests for the VCS tool plugin.
  ([`21edab1`](https://github.com/lowRISC/dvsim/commit/21edab12ec38dc586088d08e1d7f24dbcc0332c3))

- Add tests for the tool plugin system
  ([`b883b7b`](https://github.com/lowRISC/dvsim/commit/b883b7b73688f0cdde6bd50cfcbb98b07c2d177d))


## v1.0.6 (2025-11-12)

### Bug Fixes

- Report item filtering
  ([`4b5d01d`](https://github.com/lowRISC/dvsim/commit/4b5d01d761454e82e21cd34529eeb8af5ed9a4a6))

- Run and sim time precision and units
  ([`8af1207`](https://github.com/lowRISC/dvsim/commit/8af12074f27e3f6e24694691384be8b5381908a9))


## v1.0.5 (2025-11-11)

### Chores

- Nix flake update
  ([`80545d3`](https://github.com/lowRISC/dvsim/commit/80545d3c4c1f131403cb17b9fc485adf0ddb7e56))

### Refactoring

- Add JobSpec common abstraction
  ([`be1e1e1`](https://github.com/lowRISC/dvsim/commit/be1e1e1c56eb3842e75a1c6352b484a1b756fb6a))

- Migrate from Depoy.dump to JobSpec.model_dump
  ([`91ac90e`](https://github.com/lowRISC/dvsim/commit/91ac90e5a1f24f2cbeda9d1811bc95eb6b226547))


## v1.0.4 (2025-11-06)

### Code Style

- Linting, docstrings and typing
  ([`08b8e6d`](https://github.com/lowRISC/dvsim/commit/08b8e6de9827d5f2a2e7d4c493d76f097d5f4ace))

### Refactoring

- Add WorkspaceCfg
  ([`9a7a08e`](https://github.com/lowRISC/dvsim/commit/9a7a08e57d53bbf24f7b414ef84aee31c2d2b131))

- Improvements in lsf launcher
  ([`d64033d`](https://github.com/lowRISC/dvsim/commit/d64033d580b7acaba61b9fc98515e22de720dfe5))

- Make cov_db_dirs deterministic
  ([`3bb06fc`](https://github.com/lowRISC/dvsim/commit/3bb06fc14fb041a253da4d1af5ffc9989e2e63b3))

- Rename model_dump -> dump
  ([`53bbfd4`](https://github.com/lowRISC/dvsim/commit/53bbfd41ee38b7f0fcf97e07a7520573077db585))

### Testing

- Add initial CompileSim unittest
  ([`e8d5279`](https://github.com/lowRISC/dvsim/commit/e8d52791c2ac5317648cb51f495db4eb8aeca3e7))


## v1.0.3 (2025-10-30)

### Bug Fixes

- Add missing concrete implementations
  ([`49786d0`](https://github.com/lowRISC/dvsim/commit/49786d0005a35215059d540b7d9136ae9d8b1ad5))

- Remove dependency on launcher
  ([`c135fa6`](https://github.com/lowRISC/dvsim/commit/c135fa6562132cf3337a6abb17942ff361d8fe5b))

### Code Style

- Improved docstrings and linting fixes
  ([`bc1cdef`](https://github.com/lowRISC/dvsim/commit/bc1cdef82e8c8fde84ca9c10aba5731d108989d7))


## v1.0.2 (2025-10-16)

### Bug Fixes

- Remove use of feature not supported by 3.10
  ([`b8f45ef`](https://github.com/lowRISC/dvsim/commit/b8f45ef23040f961c391d94add0275b66a91b4cb))

### Chores

- Flake update
  ([`7781364`](https://github.com/lowRISC/dvsim/commit/7781364fab1980b1448b0d8a49c6b3244af9d10a))

### Continuous Integration

- Fix python matrix
  ([`a195684`](https://github.com/lowRISC/dvsim/commit/a195684ae8d2bd6733b0cad95f59e99d182b0257))


## v1.0.1 (2025-10-15)

### Bug Fixes

- Fake launcher missing abstract methods
  ([`a58fd05`](https://github.com/lowRISC/dvsim/commit/a58fd05402439a31b443fe6b8e51dc23500bc05f))

### Refactoring

- Use deployment name instead of object as dict keys
  ([`6938d34`](https://github.com/lowRISC/dvsim/commit/6938d343d9ef44cf23b333fdb066f39d6d34973c))


## v1.0.0 (2025-10-14)

### Bug Fixes

- [launcher] drop poll_freq from 1s to 0.05s for the local launcher
  ([`3628d69`](https://github.com/lowRISC/dvsim/commit/3628d693c6beba67246c754c23f1b17013afeba4))

- [wildcards] refactor and improved testing with fixes
  ([`c7d7a9a`](https://github.com/lowRISC/dvsim/commit/c7d7a9a2292b2d1d493bc9439da78f2a42590f2a))

- Circular import issue
  ([`0a1c1c3`](https://github.com/lowRISC/dvsim/commit/0a1c1c345f8b83af21b654b14d3a8abd3fdad8d4))

- Improve testing and fix issues with the fs helpers.
  ([`40c4f22`](https://github.com/lowRISC/dvsim/commit/40c4f2241a50dc7f063fa2e9991063d04556bcf0))

- Logging of timeout after wildcard eval
  ([`87e09a3`](https://github.com/lowRISC/dvsim/commit/87e09a3e579e117361f0128d97e361daa2e245ee))

- Move ipython into debug/dev/nix extra dependency groups
  ([`7b53822`](https://github.com/lowRISC/dvsim/commit/7b53822f0f6aa3c401074853ec8580044731ecfa))

- Nix devshell
  ([`995a57c`](https://github.com/lowRISC/dvsim/commit/995a57cbb08bd4308cd6c36df1af93069ec86aef))

- Regression
  ([`9c1bf17`](https://github.com/lowRISC/dvsim/commit/9c1bf174676d0beb7898b604a3fca939b1e4ae01))

- Remove shebangs from scripts
  ([`597c7d5`](https://github.com/lowRISC/dvsim/commit/597c7d584c7dcd29c4241978c9bf274babc3c71a))

- Remove unused Bazel BUILD file
  ([`60dcb91`](https://github.com/lowRISC/dvsim/commit/60dcb91c78b4ad69e3799e94e029c0b1d2ef69be))

- Results refactor name clash
  ([`073f9a7`](https://github.com/lowRISC/dvsim/commit/073f9a7a978b021e94a794a68bbe2d034f5985d7))

- Style.css needs to be in the flow dir
  ([`a181bdd`](https://github.com/lowRISC/dvsim/commit/a181bdde42bc7e39418dc5a4c0773bdf81f8db3e))

### Build System

- [pytest] update config to ignore scratch dir when collecting tests
  ([`c484ac6`](https://github.com/lowRISC/dvsim/commit/c484ac6b023eaea91723235060e0ae2e5a99e339))

### Code Style

- [tests] disable pedantic rules for test files.
  ([`3a7709d`](https://github.com/lowRISC/dvsim/commit/3a7709da9403eee1f50762579d8a0520d6cd91c4))

- Disable TRY003
  ([`fe7fecd`](https://github.com/lowRISC/dvsim/commit/fe7fecd7bd07ef61b5410ab1ca6a09fc65d46880))

- Fix auto-fixable PTH issues
  ([`cc26b34`](https://github.com/lowRISC/dvsim/commit/cc26b342c8fa8641a0b364424bf299d34290e619))

- Fix instances of A001
  ([`bfed9d4`](https://github.com/lowRISC/dvsim/commit/bfed9d4f5f3bb535d5713d16b2eb0542d2d3ead8))

- Fix instances of N806
  ([`0cf67f1`](https://github.com/lowRISC/dvsim/commit/0cf67f149199115c9cbd111db7c5846aa331a663))

- Fix instances of N816
  ([`6e76ad7`](https://github.com/lowRISC/dvsim/commit/6e76ad704d7aaf972b54696bd268057d1ef7c976))

- Fix instances of N818
  ([`36ec821`](https://github.com/lowRISC/dvsim/commit/36ec821104de32a895b819828dcfa15530e186ae))

- Fix N803 issues and enable rule
  ([`60b16d7`](https://github.com/lowRISC/dvsim/commit/60b16d7a5966f484e75536134ef5a45f04a5e9a4))

- Remove uneccesery variable
  ([`a5290dc`](https://github.com/lowRISC/dvsim/commit/a5290dcb13475cf1da232b0ff46f4d2884b9ec9b))

### Continuous Integration

- Add an action to get a lowrisc-ci app installation access token
  ([`16a9508`](https://github.com/lowRISC/dvsim/commit/16a9508ea6954d4f3634ba8587beafe85417caa1))

- Add automated release action based on python-semantic-release / conventional commits
  ([`46dc514`](https://github.com/lowRISC/dvsim/commit/46dc514e13c10137a4704929d794ba6281a233bf))

- Copy over check for commit metadata
  ([`1dc0673`](https://github.com/lowRISC/dvsim/commit/1dc067397713edcaa56097038f716ecea6462fd2))

- Github actions to version and creation of the release
  ([`fc763d4`](https://github.com/lowRISC/dvsim/commit/fc763d4f220a6d8ad2a290bcaa639672d9c2e0cb))

### Features

- [launcher] add fake launcher to produce random results
  ([`fd5aed1`](https://github.com/lowRISC/dvsim/commit/fd5aed144be4785b48e918823198c6d548a142a7))

- Add deployment object dump debug feature
  ([`f682788`](https://github.com/lowRISC/dvsim/commit/f68278806eb4d860c30723510feb842d8a2b0efd))

- Added configuration options for release
  ([`d7ed748`](https://github.com/lowRISC/dvsim/commit/d7ed74830c83c1acc25ca60eb43144ee1cb19c19))

### Refactoring

- [flow] module rename dvsim.CdcCfg -> dvsim.flow.cdc
  ([`d93fdce`](https://github.com/lowRISC/dvsim/commit/d93fdce5942c7c0d57c4c57f8daa5a2230c3d898))

- [flow] module rename dvsim.CfgFactory -> dvsim.flow.factory
  ([`a47d9e2`](https://github.com/lowRISC/dvsim/commit/a47d9e21ef906a21902f9071484f097a37081fe0))

- [flow] module rename dvsim.FlowCfg -> dvsim.flow.base
  ([`4ec6081`](https://github.com/lowRISC/dvsim/commit/4ec60819f789e65fec0a1bcb404a875b3169becc))

- [flow] module rename dvsim.FormalCfg -> dvsim.flow.formal
  ([`c59fa69`](https://github.com/lowRISC/dvsim/commit/c59fa69d24a3c58c27386c92965ac425a6400c6f))

- [flow] module rename dvsim.LintCfg -> dvsim.flow.lint
  ([`31a5b15`](https://github.com/lowRISC/dvsim/commit/31a5b1549413dba9769ba614218b29a0793e4fe0))

- [flow] module rename dvsim.OneShotCfg -> dvsim.flow.one_shot
  ([`8ff0f09`](https://github.com/lowRISC/dvsim/commit/8ff0f0900fc3b639eb6af821213c846ce92e2cb5))

- [flow] module rename dvsim.SimCfg -> dvsim.flow.sim
  ([`4e0c39a`](https://github.com/lowRISC/dvsim/commit/4e0c39ae9bb9569edcea6b5d3ad44953bae83845))

- [flow] module rename dvsim.SynCfg -> dvsim.flow.syn
  ([`eca83a6`](https://github.com/lowRISC/dvsim/commit/eca83a6ed0e0c1ac5c408b3954e64e1d2f002cb9))

- [job] pull out JobTime tests, improved testing and fix a few bugs
  ([`b56441f`](https://github.com/lowRISC/dvsim/commit/b56441f3fe38467bdee0880251c74e4a0047c572))

- [launcher] module rename dvsim.Launcher -> dsvsim.launcher.base
  ([`f89917b`](https://github.com/lowRISC/dvsim/commit/f89917be21157d4179de1c4d22083fcbcdfedad4))

- [launcher] module rename dvsim.LauncherFactory -> dsvsim.launcher.factory
  ([`9e90ebe`](https://github.com/lowRISC/dvsim/commit/9e90ebe16e7005d02a70f7ce6247df26cae7dea5))

- [launcher] module rename dvsim.LocalLauncher -> dsvsim.launcher.local
  ([`88f8d0d`](https://github.com/lowRISC/dvsim/commit/88f8d0d348be33d0a23ca6bf5df69e29cd44f9f1))

- [launcher] module rename dvsim.LsfLauncher -> dsvsim.launcher.lsf
  ([`f2bf778`](https://github.com/lowRISC/dvsim/commit/f2bf7783066ee78ef29a5dc9638af3a61cb0fd0f))

- [launcher] module rename dvsim.NcLauncher -> dsvsim.launcher.nc
  ([`6d2806b`](https://github.com/lowRISC/dvsim/commit/6d2806b8e423832f2276bc89dba7c62f6964b7ad))

- [launcher] module rename dvsim.SgeLauncher -> dsvsim.launcher.sge
  ([`3120ec4`](https://github.com/lowRISC/dvsim/commit/3120ec408c8269454722fc6ec12f07db110b8de9))

- [launcher] module rename dvsim.SlurmLauncher -> dsvsim.launcher.slurm
  ([`0d81e22`](https://github.com/lowRISC/dvsim/commit/0d81e229cdf983f2b24d3df235d39655782fb40c))

- [logging] pull out logging setup from the main function
  ([`1e75b9a`](https://github.com/lowRISC/dvsim/commit/1e75b9a9797d3053f3db0f8e5967f53f48b49360))

- [logging] use custom logger rather than the base logger
  ([`1aa0541`](https://github.com/lowRISC/dvsim/commit/1aa0541c7b68d33bac27f7f0aeb3e4ff4696a673))

- [publish] remove the old report publishing mechanisms
  ([`c9cd75f`](https://github.com/lowRISC/dvsim/commit/c9cd75f95e74809ac530264a62a8b3a3195093d7))

- [report] remove old report dir versioning
  ([`96ff3d5`](https://github.com/lowRISC/dvsim/commit/96ff3d57938ab18942b418f75770c25650418771))

- [reporting] remove unnesesery latest dir for reporting
  ([`de0fa37`](https://github.com/lowRISC/dvsim/commit/de0fa375028dbc22fd6b97370f0111ebce33c1e0))

- [typing] add typing to the Scheduler
  ([`b796d3c`](https://github.com/lowRISC/dvsim/commit/b796d3ced10a9bf80ebd94b0070cddfc6b92e152))

- [utils] convert utils to a package
  ([`08bcbdc`](https://github.com/lowRISC/dvsim/commit/08bcbdcefb33f7cf900971e1b6ed8d3a88527ccc))

- [utils] split out remaining utils into modules
  ([`64ce14c`](https://github.com/lowRISC/dvsim/commit/64ce14cfba2074f83e76c2047ae2f39237765295))

- Improve and add typing to status printer
  ([`d097727`](https://github.com/lowRISC/dvsim/commit/d0977274057b3ccf315ddd6724f7ff85f9de4f3f))

- Initial detanglement of deployment objects
  ([`1102d8d`](https://github.com/lowRISC/dvsim/commit/1102d8ddcd4743b5e20fab571f89356c9fb914cc))

- Rename dvsim.MsgBucket -> dvsim.msg_bucket
  ([`834f9e7`](https://github.com/lowRISC/dvsim/commit/834f9e75adbe1c08687eb97c85e475d0dfca8a2d))

- Rename dvsim.MsgBuckets -> dvsim.msg_buckets
  ([`3ae5918`](https://github.com/lowRISC/dvsim/commit/3ae591851f5c201346bd6d182bd59f832c81b9ec))

- Rename dvsim.Regression -> dvsim.regression
  ([`b79b5f4`](https://github.com/lowRISC/dvsim/commit/b79b5f45009e28d9c76c99fbd956bfb023f37664))

- Rename dvsim.Scheduler -> dvsim.scheduler
  ([`afbcaa1`](https://github.com/lowRISC/dvsim/commit/afbcaa17759571c845a6e93d6fb94cf720125a93))

- Rename dvsim.SimResults -> dvsim.sim_results
  ([`b2e7813`](https://github.com/lowRISC/dvsim/commit/b2e7813e1aa1976e22414ebccb069884c8639e42))

- Rename dvsim.StatusPrinter -> dvsim.utils.status_printer
  ([`14c4917`](https://github.com/lowRISC/dvsim/commit/14c4917c9aa2a44aaaf1071e1ca5b19cf895bb89))

- Rename dvsim.Test/Testplan -> dvsim.utils.test/testplan
  ([`9b4f89f`](https://github.com/lowRISC/dvsim/commit/9b4f89fcefa43e291998d26474678e066e5e4431))

- Rename dvsim.Timer -> dvsim.utils.timer
  ([`41366ad`](https://github.com/lowRISC/dvsim/commit/41366adcf8ef3b1c433d7880e66bf0045fce3a26))

- Rename remaining modules and enable N999 lint
  ([`8dad466`](https://github.com/lowRISC/dvsim/commit/8dad4663ec4894863a0d095060f984df5cdb9cd4))

### Testing

- Add cli run test
  ([`f87b7e6`](https://github.com/lowRISC/dvsim/commit/f87b7e608820c5f1506c287ae6f0a647f561ea43))


## v0.1.0 (2025-09-09)

- Initial Release
