# CHANGELOG

<!-- version list -->

## v1.33.1 (2026-05-01)

### Bug Fixes

- Local job timeout reported as job being killed
  ([`f734f22`](https://github.com/lowRISC/dvsim/commit/f734f22e78d215f5711c643570b718a7107f4061))

- Timed out jobs now go through RuntimeBackend._finish_job
  ([`3058428`](https://github.com/lowRISC/dvsim/commit/3058428315ff2bd231660ec381ddac61c5d5d62c))


## v1.33.0 (2026-04-29)

### Continuous Integration

- Bump all checkout actions from v4 to v6
  ([`cccf592`](https://github.com/lowRISC/dvsim/commit/cccf59244613e1ff4d845b4e5fa376d45f9e75a3))

- Bump all download-artifact actions from v4 to v8
  ([`2435507`](https://github.com/lowRISC/dvsim/commit/2435507e2b31f3f25c58c5ac56cb12afd971a6ae))

- Bump all upload-artifact actions from v4 to v7
  ([`650de78`](https://github.com/lowRISC/dvsim/commit/650de785f98e0c51ca6b304f16f484176e7fc35f))

- Bump set-uv action from v6 to v8
  ([`d5d3992`](https://github.com/lowRISC/dvsim/commit/d5d399292d2df06849e60b960ab5416d1fba794a))

### Features

- **ci**: Enforce conventional commits
  ([`547ce37`](https://github.com/lowRISC/dvsim/commit/547ce37d55d44e9b429962979fd62c6e41fbc054))


## v1.32.0 (2026-04-17)

### Bug Fixes

- Handle missing score metric in Xcelium sim tool coverage summary
  ([`1cc4dfc`](https://github.com/lowRISC/dvsim/commit/1cc4dfc384da98509cc0ea3f52973f6ddcffe4fe))

- Remove superfluous `Path` construction in xcelium sim tool
  ([`b4c1c24`](https://github.com/lowRISC/dvsim/commit/b4c1c2417838a3e0299fb747bda92e134de30b5e))

- Xcelium sim tool pyright/ruff errors
  ([`5cd1ea1`](https://github.com/lowRISC/dvsim/commit/5cd1ea10180705240ff494f847e966b38badf3a5))

### Features

- Add command line resource options & integrate with the base flow
  ([`bdc4098`](https://github.com/lowRISC/dvsim/commit/bdc4098a6d4db9a1884dc1a1a0f3cd68a0c65555))

- Integrate resources into the scheduler to limit parallelism
  ([`f205446`](https://github.com/lowRISC/dvsim/commit/f2054466243fbbe278f2dd97d15c2bcd3822a7f3))

- Introduce ResourceProvider abstraction and a ResourceManager
  ([`3713a07`](https://github.com/lowRISC/dvsim/commit/3713a078fbd14b452a901204eb432283519380e3))

### Refactoring

- Change Scheduler `max_parallelism` type
  ([`d3494a3`](https://github.com/lowRISC/dvsim/commit/d3494a3c35147fc5c378f7147d19495707cb6ae6))

### Testing

- Add scheduler tests for resource-level parallelism
  ([`030a584`](https://github.com/lowRISC/dvsim/commit/030a58440e6981b7bcbeca8ede4bb98edbd015f2))


## v1.31.0 (2026-04-16)

### Bug Fixes

- Z01x sim tool build time parsing
  ([`b8d553c`](https://github.com/lowRISC/dvsim/commit/b8d553c8956c66ce176a899edb68c76423780f35))

### Continuous Integration

- Use lowrisc/ci-actions for token acquisition
  ([`95f8269`](https://github.com/lowRISC/dvsim/commit/95f826983e4c23665aa328f3ba2349a05eb91531))

### Documentation

- Correct sim tool doc messages
  ([`ef416e4`](https://github.com/lowRISC/dvsim/commit/ef416e42f13d58994fa18d48888d5b21b6772c5e))

### Features

- Add z01x runtime and simulated time log parsing
  ([`3311a96`](https://github.com/lowRISC/dvsim/commit/3311a9692cc1fc90f1a6ea8d8eec9bea3fb9e11a))

### Refactoring

- Replace simulation tool `SyntaxError` with `RuntimeError`
  ([`784a9c6`](https://github.com/lowRISC/dvsim/commit/784a9c6bc38ac60fff55d55132aeebe5af2f2bb4))


## v1.30.1 (2026-04-10)

### Bug Fixes

- Stop stdout/stderr line buffering in local interactive jobs
  ([`7098bbf`](https://github.com/lowRISC/dvsim/commit/7098bbf66c5fa7ede88667cd769ba7256de3b85d))


## v1.30.0 (2026-04-10)

### Bug Fixes

- Give test `FakeSimCfg` a flow attribute
  ([`28e60af`](https://github.com/lowRISC/dvsim/commit/28e60afc2e73aaf391b8e6800d6fd00c846cbf82))

### Features

- Add initial VC Z01X simulation tool support
  ([`73c6e07`](https://github.com/lowRISC/dvsim/commit/73c6e074426010ac6bdac059951027dedbca3cc4))

- Enable options for post-build commands
  ([`9b28d2f`](https://github.com/lowRISC/dvsim/commit/9b28d2f94eaa3cc4343676905de43b0e95f24748))

### Refactoring

- Make `Deploy.exports` type more specific.
  ([`e51132f`](https://github.com/lowRISC/dvsim/commit/e51132f031484a6af1012274a181a46f3e186381))


## v1.29.1 (2026-04-10)

### Refactoring

- Pull out the run_scheduler to common place
  ([`7bb17c7`](https://github.com/lowRISC/dvsim/commit/7bb17c72920542d21e889230770da0b5c0eed58f))


## v1.29.0 (2026-04-09)

### Features

- Remove computed symlink dirs from the `JobSpec` and `FlowCfg`
  ([`25017ee`](https://github.com/lowRISC/dvsim/commit/25017ee5ea03b06a19e711272c203878e7a4aab4))

### Refactoring

- Move `workspace_cfg` to the base flow
  ([`8d3323a`](https://github.com/lowRISC/dvsim/commit/8d3323a7136e8cba96bf992b628a5fa5588eb70b))

- Move status symlink directory creation to the `LogManager`
  ([`e23e6ba`](https://github.com/lowRISC/dvsim/commit/e23e6ba8cf065c92c47398cfc1ebdda3a659d74b))

- Remove output directory status symlinking from the launchers
  ([`e0ad0a4`](https://github.com/lowRISC/dvsim/commit/e0ad0a43ae725b02aad1b6af2d2cad191909458e))

- Remove test dependencies on `JobSpec.links`
  ([`9a92b89`](https://github.com/lowRISC/dvsim/commit/9a92b89f397f131c849d8ab15a285b079e419479))


## v1.28.1 (2026-04-09)

### Bug Fixes

- Delayed status printer start on slow machines
  ([`4af00e9`](https://github.com/lowRISC/dvsim/commit/4af00e9b6685295c7b8d5d6ed11f037e0182d6b8))


## v1.28.0 (2026-04-09)

### Features

- Use logical CPUs minus one as max_parallel default instead of 16
  ([`18b649e`](https://github.com/lowRISC/dvsim/commit/18b649e93be914c71a13048654761f03bcd44b30))


## v1.27.1 (2026-04-09)

### Refactoring

- Improve the error message if given a sim item with no matches
  ([`012178f`](https://github.com/lowRISC/dvsim/commit/012178fa0fc30ff51a33d9524e7853397858fa2a))


## v1.27.0 (2026-04-08)

### Features

- Remove unused `--no-rerun` option
  ([`134420e`](https://github.com/lowRISC/dvsim/commit/134420e961f583b2cecab55b0d60ac8f77c7ad63))


## v1.26.3 (2026-04-07)

### Refactoring

- Rewrite how OneShotCfg.build_modes gets constructed
  ([`c471598`](https://github.com/lowRISC/dvsim/commit/c47159832a7868ac5b8d80cd6d81956d65a16b67))

- Rewrite Mode.create_modes as a class method
  ([`a23741e`](https://github.com/lowRISC/dvsim/commit/a23741e724dcbb0b699a7a7af6305ec2c5f7c783))


## v1.26.2 (2026-04-07)

### Refactoring

- Tidy up the last few Ruff problems in one_shot.py
  ([`b2de3fc`](https://github.com/lowRISC/dvsim/commit/b2de3fc587a6db03da8ae7aa3b53b0b8871a47aa))


## v1.26.1 (2026-04-07)

### Bug Fixes

- Move initial async status printer update
  ([`c29abfb`](https://github.com/lowRISC/dvsim/commit/c29abfb1f16092a15f116d3b2161cefd81227fb8))


## v1.26.0 (2026-04-07)

### Features

- Async_core -> core & async_status_printer -> status_printer
  ([`95193f1`](https://github.com/lowRISC/dvsim/commit/95193f17aa028c8f83c2c93a7261340f1fdec9c0))

- Remove `Timer` utility
  ([`76947ab`](https://github.com/lowRISC/dvsim/commit/76947ab53b4d84d3408aced58e219329e2c0be09))

- Remove legacy LocalLauncher, FakeLauncher and Launcher factory
  ([`9e7f321`](https://github.com/lowRISC/dvsim/commit/9e7f321de9668fcc5200840532db15f74cb78ce9))

- Remove the old scheduler and status printer
  ([`05cbad4`](https://github.com/lowRISC/dvsim/commit/05cbad46bbbd2da0404f10f3ee13a19d13a0b1b3))

- Switch to use the async scheduler interface
  ([`0daa4eb`](https://github.com/lowRISC/dvsim/commit/0daa4ebe3d71abd665d7c6faf95ddf13cb22a7df))

### Testing

- Add 2 async scheduler tests for parallelism & prioritization
  ([`70e5a0d`](https://github.com/lowRISC/dvsim/commit/70e5a0dcf1fa5272330ff5518d4bf2d80368b28f))

- Add `pytest-asyncio` dependency
  ([`efc45b7`](https://github.com/lowRISC/dvsim/commit/efc45b73be2c05b7932c116384f164d23163428e))

- Convert scheduler tests to use the new async scheduler
  ([`3343eb8`](https://github.com/lowRISC/dvsim/commit/3343eb8189040ae1b33d4ded68634636008467b5))


## v1.25.0 (2026-04-07)

### Features

- Implement fake runtime backend with fake coverage results
  ([`c0748a4`](https://github.com/lowRISC/dvsim/commit/c0748a4f31cbfcc3496d9fe9fd38426ffe66cd0d))


## v1.24.0 (2026-04-07)

### Features

- Improve default scheduler prioritization function
  ([`3ef09da`](https://github.com/lowRISC/dvsim/commit/3ef09dad18d65f2eb39f6523872dba8b644f563f))


## v1.23.6 (2026-04-07)

### Bug Fixes

- Apply `--max-odirs` to `RuntimeBackend` as well
  ([`4a6fb15`](https://github.com/lowRISC/dvsim/commit/4a6fb1513883f3c28eb06d731cee2029450b414a))


## v1.23.5 (2026-04-06)

### Refactoring

- Be more careful with variants in OneShotCfg.gen_results
  ([`e662759`](https://github.com/lowRISC/dvsim/commit/e6627596d256a37796c0435669eaea579848b168))


## v1.23.4 (2026-04-06)

### Refactoring

- Make the typing clearer in Deploy._process_exports
  ([`ed6beb9`](https://github.com/lowRISC/dvsim/commit/ed6beb9e7f52c7a293de96a33877401acc4f420e))


## v1.23.3 (2026-04-06)

### Refactoring

- Fix types of JobSpec.timeout_mins, JobSpec.timeout_secs
  ([`5fe1dbc`](https://github.com/lowRISC/dvsim/commit/5fe1dbc0d6e9a1dbe65577f76cc945ce8c08883e))


## v1.23.2 (2026-04-06)

### Refactoring

- Move tool name to FlowCfg
  ([`51e3655`](https://github.com/lowRISC/dvsim/commit/51e36557f8a6357452884769f417527e5ead747c))


## v1.23.1 (2026-04-06)

### Refactoring

- Explicitly add proj_root to FlowCfg
  ([`c06170e`](https://github.com/lowRISC/dvsim/commit/c06170ee510061c29499ed624ef4ec2703ef3f76))

### Testing

- Add `pytest-mock` dependency
  ([`5514be4`](https://github.com/lowRISC/dvsim/commit/5514be441a36d39bbb891a84f7db8f4b00151658))

- Add runtime backend registry tests
  ([`6b19dc7`](https://github.com/lowRISC/dvsim/commit/6b19dc74297200a942a43867850aa3fd6d323636))


## v1.23.0 (2026-04-06)

### Bug Fixes

- Check if coverage report exists in `CovReport`
  ([`424dfca`](https://github.com/lowRISC/dvsim/commit/424dfca3e37751e1492dacb6c34b0ead8903ed64))

### Features

- Connect instrumentation to the new async scheduler
  ([`347419d`](https://github.com/lowRISC/dvsim/commit/347419d11473ad155fde3ed039271d105eb8a37f))

- Implement initial async scheduler integration
  ([`b222868`](https://github.com/lowRISC/dvsim/commit/b2228687416bddbf001031aadf1ddb2be45510a1))

- Integrate async status printers with the async scheduler
  ([`67897f0`](https://github.com/lowRISC/dvsim/commit/67897f06ef5a80949645f04fea0becfc986bbf04))

- Introduce `LogManager` and connect it to the async scheduler
  ([`48bee84`](https://github.com/lowRISC/dvsim/commit/48bee84f62f996e17e07a968b1dbaf7883a421ee))

- Introduce runtime backend registry
  ([`7da9684`](https://github.com/lowRISC/dvsim/commit/7da96845cc249d8ac3c0eb0afce738c22f25dda1))


## v1.22.0 (2026-04-06)

### Features

- Implement new async base `StatusPrinter` class
  ([`d6068eb`](https://github.com/lowRISC/dvsim/commit/d6068eb7ae06031d52d89c32699d536a88be136f))

- Port `EnlightenStatusPrinter` to the async interface
  ([`4061086`](https://github.com/lowRISC/dvsim/commit/40610864bd9c1597639df496f83f33b76ea88c81))

- Port `TtyStatusPrinter` to the new async interface
  ([`906d00f`](https://github.com/lowRISC/dvsim/commit/906d00f23b2680e45e14355e47ab47b39df5cac1))

### Refactoring

- Reorganize time utilities
  ([`f7af42d`](https://github.com/lowRISC/dvsim/commit/f7af42d979206441d2fc06dd5e2022b0d3340104))


## v1.21.0 (2026-04-06)

### Features

- Add optional backend field to the `JobSpec` model
  ([`bf28dac`](https://github.com/lowRISC/dvsim/commit/bf28dace73af06d2c62168e29bd2abaa54cdc0a7))

- Introduce a new `SCHEDULED` job status
  ([`3efc473`](https://github.com/lowRISC/dvsim/commit/3efc47329cd125be09b65e5e52f7c82d689bdfa1))

- Introduce new async scheduler
  ([`40ce9c0`](https://github.com/lowRISC/dvsim/commit/40ce9c0489b9822a4da0fac47afc2e9ca8e4b2f5))


## v1.20.0 (2026-04-06)

### Features

- Add `LocalRuntimeBackend` backend
  ([`22c795d`](https://github.com/lowRISC/dvsim/commit/22c795d7917396ff018ec928fd7f42cc5f96ac9c))

- Port core launcher base functionality to the `RuntimeBackend` base
  ([`408e5bb`](https://github.com/lowRISC/dvsim/commit/408e5bb751fab0b924153f1f9fdc83bebfe68b81))


## v1.19.7 (2026-04-03)

### Refactoring

- Tidy up the last few Ruff problems in deploy.py
  ([`f83c7e1`](https://github.com/lowRISC/dvsim/commit/f83c7e1881e5ea90042bf0d693170caaebfbc240))


## v1.19.6 (2026-04-03)

### Refactoring

- Explicitly give types to some fields in Deploy subclasses
  ([`7c2195e`](https://github.com/lowRISC/dvsim/commit/7c2195e0a1ee4ebbe63e8d7c2775d64eb3c1944e))


## v1.19.5 (2026-04-03)

### Refactoring

- Add more strictly typed "sim_cfg" to some Deploy classes
  ([`34653b2`](https://github.com/lowRISC/dvsim/commit/34653b2dd9f02221e52056ce28e919940563b21c))


## v1.19.4 (2026-04-03)

### Refactoring

- Correct the type for RunMode.build_mode
  ([`7bc25f6`](https://github.com/lowRISC/dvsim/commit/7bc25f651e2710e9ba14d3ce00dd6749bc4212e1))


## v1.19.3 (2026-04-03)

### Bug Fixes

- Correct the type for Deploy.init
  ([`c831123`](https://github.com/lowRISC/dvsim/commit/c831123ad39ec9f8a669a5ee56ae8c0343da8251))

### Refactoring

- Move the "name" field up to FlowCfg
  ([`845a518`](https://github.com/lowRISC/dvsim/commit/845a5183f87f6d4f1594356570634daf3740e00e))


## v1.19.2 (2026-04-02)

### Bug Fixes

- Move revision info retrieval to the base `FlowCfg`
  ([`5524219`](https://github.com/lowRISC/dvsim/commit/5524219b5740b4138816a7d289d4284fe00a66d7))


## v1.19.1 (2026-04-02)

### Bug Fixes

- Use correct shorthand for 'Running' in the scheduler
  ([`3a3927d`](https://github.com/lowRISC/dvsim/commit/3a3927d08936292d0f9fa2c5af1e00ad6142ddee))


## v1.19.0 (2026-04-01)

### Features

- Add new `JobStatusInfo` model
  ([`63e8d12`](https://github.com/lowRISC/dvsim/commit/63e8d127636cea50e917e01f4e27f6bef607aea0))

- Introduce `JobSpec.id` property
  ([`c874331`](https://github.com/lowRISC/dvsim/commit/c8743313ad6042107e4b2354c6b6039fb9e8a75b))

- Introduce `LegacyLauncherAdapter` runtime backend
  ([`65df3d6`](https://github.com/lowRISC/dvsim/commit/65df3d66f7104009025d87b4688409045ffca446))

- Introduce abstract `RuntimeBackend` base class
  ([`cbb46d2`](https://github.com/lowRISC/dvsim/commit/cbb46d2d97e6aa74eeb491505f64298f3cc71b1d))


## v1.18.0 (2026-04-01)

### Features

- Rename 'Dispatched' job status to 'Running'
  ([`66f8205`](https://github.com/lowRISC/dvsim/commit/66f8205b94ef12d661927c0cf8f90ea9cb5d3ec8))

### Refactoring

- Create status link directories from the JobStatus Enum
  ([`04f6a9b`](https://github.com/lowRISC/dvsim/commit/04f6a9ba0a4fa1c75cf265f4018eb067c7eecb3d))

- Move `print_msg_list` to a separate `print` util
  ([`3ee54b9`](https://github.com/lowRISC/dvsim/commit/3ee54b927e74da67fe58262bdfa1cb97f87903f9))

- Move scheduler & status printer into separate module
  ([`ef44a6a`](https://github.com/lowRISC/dvsim/commit/ef44a6a7e0e090e6f6f6729cb53531cb9ce0ab82))

- Rename `JobStatus.ended` to `JobStatus.is_terminal`
  ([`25aab7f`](https://github.com/lowRISC/dvsim/commit/25aab7fae66c718ea031275e3942939894cd7436))


## v1.17.4 (2026-04-01)

### Refactoring

- Make timeout seconds a `JobSpec` property
  ([`ef48cc7`](https://github.com/lowRISC/dvsim/commit/ef48cc72c33e5e0d5efa349bc55a7627801bbddc))

- Pass `renew_odir` through the JobSpec instead of `pre_launch`
  ([`a57a94c`](https://github.com/lowRISC/dvsim/commit/a57a94c6a7398f4858ff91578aa8f807b008ae9d))

- Remove `pre_launch` Launcher inversion of control
  ([`b65fdc7`](https://github.com/lowRISC/dvsim/commit/b65fdc7768ef4eb164ac0ec1716e16a97a76cc27))


## v1.17.3 (2026-03-30)

### Bug Fixes

- Tee interactive job stdout/stderr to the log file
  ([`6d1f83c`](https://github.com/lowRISC/dvsim/commit/6d1f83c336a582dba69b768cbe30bf01744f2d74))

### Refactoring

- Remove `gui` attribute from the `JobSpec` model
  ([`7fa03ed`](https://github.com/lowRISC/dvsim/commit/7fa03ed64d2ec43b3f8d11748a4c6ecc39209b4e))


## v1.17.2 (2026-03-30)

### Bug Fixes

- Sim flow result pass/total count aggregation
  ([`48ec7ba`](https://github.com/lowRISC/dvsim/commit/48ec7ba112fe9ca6ebff3936e170c5a0852756cb))


## v1.17.1 (2026-03-30)

### Bug Fixes

- Restore RunTest simulation time parsing
  ([`8ebb0c1`](https://github.com/lowRISC/dvsim/commit/8ebb0c116adbec46e14f71cceba326bf6ab4c0bc))

### Refactoring

- Use format string for local launcher log instead of fstring
  ([`bdbf0b4`](https://github.com/lowRISC/dvsim/commit/bdbf0b42f093cf9669a1b2bfc18665e2c32ffa5e))

### Testing

- Expect a ValueError on a dependency cycle
  ([`0d83b97`](https://github.com/lowRISC/dvsim/commit/0d83b9730698e2648e099165ada323ed38bedd2d))

- Fix & improve status checks in scheduler job dependency tests
  ([`f05d71d`](https://github.com/lowRISC/dvsim/commit/f05d71d4547ef865132ed72ec143fd00e8255bb9))

- Fix `test_job_priority` scheduler test
  ([`6054386`](https://github.com/lowRISC/dvsim/commit/6054386aca052f3a4a165d0312c7560b7f7cdc2d))

- Remove `test_same_name_different_targets`
  ([`f4256f1`](https://github.com/lowRISC/dvsim/commit/f4256f112cbb11529f99ce5a4c75d2792cd7f5ef))


## v1.17.0 (2026-03-27)

### Bug Fixes

- Ensure default terminal restored after SIGINT with Enlighten
  ([`d534fbd`](https://github.com/lowRISC/dvsim/commit/d534fbd80d9d86b04c75a6659de0ce43d3a2b0aa))

### Features

- Expand Enlighten running status truncation to terminal width
  ([`e1b5fa9`](https://github.com/lowRISC/dvsim/commit/e1b5fa972f14aeaff2c4f2fe960cc4954bd5138f))


## v1.16.3 (2026-03-27)

### Bug Fixes

- Round RSS byte averages in resource instrumentation
  ([`519b065`](https://github.com/lowRISC/dvsim/commit/519b0656dd75883c90780791a50637a32f72f89c))

### Refactoring

- Switch to `time.perf_counter` for instrumentation
  ([`bd4b77d`](https://github.com/lowRISC/dvsim/commit/bd4b77d61544248f3b15d13761dbc6739d792804))


## v1.16.2 (2026-03-27)

### Bug Fixes

- Stop adding build job dependencies if running with --run-only
  ([`96735a1`](https://github.com/lowRISC/dvsim/commit/96735a1bce6d9aeb2ea7eab275d13f85681ee12f))


## v1.16.1 (2026-03-27)

### Bug Fixes

- Document `--interactive` reseed assumption
  ([`788ea25`](https://github.com/lowRISC/dvsim/commit/788ea254eeb2a20d59379b118474c376cffcd87a))


## v1.16.0 (2026-03-17)

### Features

- Add dashboard json
  ([`2493bc4`](https://github.com/lowRISC/dvsim/commit/2493bc417b964cadb342285d12a1e30b8c379726))

- Generate badges for test reports
  ([`92b8f44`](https://github.com/lowRISC/dvsim/commit/92b8f44eb0e96e1d1ac16678b7e1a0c24b8b3200))


## v1.15.0 (2026-03-13)

### Features

- Add dashboard generation
  ([`2c3f4af`](https://github.com/lowRISC/dvsim/commit/2c3f4af2203ff609ad48728fbcdf14b65e2a8773))

### Refactoring

- Move out the static file content renderer
  ([`241baf5`](https://github.com/lowRISC/dvsim/commit/241baf5bcab361f1fb0bb155af059cfc957d37ee))


## v1.14.2 (2026-03-12)

### Bug Fixes

- Links in markdown report when proj-root specified
  ([`2a8d15a`](https://github.com/lowRISC/dvsim/commit/2a8d15a48a77852f46135efc3cc73ccc664b73ad))

- Remove old FlowResults class
  ([`6daf94a`](https://github.com/lowRISC/dvsim/commit/6daf94af9c3217118b40161ea03a283c2a688ca7))

### Refactoring

- Separate out summary from the full results
  ([`42f5a65`](https://github.com/lowRISC/dvsim/commit/42f5a65777a966da2bc853e220a5a977b7b58d9b))


## v1.14.1 (2026-03-12)

### Bug Fixes

- Set UV_PYTHON in .envrc for NixOS direnv users
  ([`fdd69e9`](https://github.com/lowRISC/dvsim/commit/fdd69e9cb2192987d92854723e71f70a4e48ac8a))


## v1.14.0 (2026-03-10)

### Features

- Add Markdown block report generation for CLI
  ([`531bbaa`](https://github.com/lowRISC/dvsim/commit/531bbaa6db8224cd601574d70f0d30347edfb06b))

- Add Markdown summary report generation for CLI
  ([`148e2dc`](https://github.com/lowRISC/dvsim/commit/148e2dc51b183780c3caa276fe1da5775a90c29a))

- Add stubbed Markdown report renderer with CLI summary
  ([`957f166`](https://github.com/lowRISC/dvsim/commit/957f16668dc25def3caacfd0d3b06c5591e47242))

- Add the coverage report dashboard page to sim summary
  ([`0e788b0`](https://github.com/lowRISC/dvsim/commit/0e788b0f1c78e83d71a661d465614f36650634a7))

- Record the testplan reference in the sim result summary
  ([`848d4f1`](https://github.com/lowRISC/dvsim/commit/848d4f185c34b6285e69f39ec3674b2cdce89961))

### Refactoring

- Store qualified name and log path in bucket items
  ([`76feedf`](https://github.com/lowRISC/dvsim/commit/76feedf393aa9cb8541d78f0bf185dc2e84ef571))


## v1.13.0 (2026-03-10)

### Bug Fixes

- Git commit and SimCfg revision info
  ([`d6d53f6`](https://github.com/lowRISC/dvsim/commit/d6d53f6bf513c5891829106745b31ca831920c8e))

### Features

- Add short option to git commit hash retrieval
  ([`4923681`](https://github.com/lowRISC/dvsim/commit/49236813c00379c73d8b03e08021aa44ca657bb6))

### Refactoring

- Add sim report renderer abstraction
  ([`5ded4ae`](https://github.com/lowRISC/dvsim/commit/5ded4aebfd0b71ebc5d51821865d974d024f79a6))


## v1.12.0 (2026-03-10)

### Bug Fixes

- Summary/CSS for block HTML reports
  ([`9653798`](https://github.com/lowRISC/dvsim/commit/9653798f0066b6cac09e9ce4626451800551e668))

### Features

- Add build seed to the sim result reports
  ([`241fdb3`](https://github.com/lowRISC/dvsim/commit/241fdb334e9f947124268407eade30fc4a5f0645))

- Replace HTMX-driven DOM injection with templated navigable pages
  ([`8d46972`](https://github.com/lowRISC/dvsim/commit/8d46972629a0df8b2818b52330a171a3388e8df2))

- Summary HTML report navbar brand redirects to root
  ([`ed67636`](https://github.com/lowRISC/dvsim/commit/ed676365c26d4482eeee1896b14f11c11c628f56))

### Refactoring

- Convert HTML wrapper indentation to spaces
  ([`6768ec7`](https://github.com/lowRISC/dvsim/commit/6768ec7fb1a1894b6d4e5f6ef1c75b68535b3448))

- Remove deploy cov_results table
  ([`f49a968`](https://github.com/lowRISC/dvsim/commit/f49a9684e9b8b9fdcde6dae3eaeb1a8f8e86e004))


## v1.11.5 (2026-03-06)

### Bug Fixes

- Calculate git url for reports
  ([`aeac114`](https://github.com/lowRISC/dvsim/commit/aeac114acda339038d901a803a07337c2fafde4b))

### Chores

- Update nix flake to pull in latest ruff version
  ([`0b461c0`](https://github.com/lowRISC/dvsim/commit/0b461c0b656a2f87122f2d10332ecc359ce797e3))


## v1.11.4 (2026-03-05)

### Bug Fixes

- Broken ruff lint
  ([`d10d401`](https://github.com/lowRISC/dvsim/commit/d10d4011c75b73c26d01f05c94687ecdab8881c6))


## v1.11.3 (2026-03-05)

### Bug Fixes

- Attach DVSim version to individual block reports
  ([`df52926`](https://github.com/lowRISC/dvsim/commit/df529263e8c547255a24cf3810155ad03ff6a4d7))

- Avoid duplicate block report generation for primary configs
  ([`3e92f48`](https://github.com/lowRISC/dvsim/commit/3e92f48f7c6377fc1cf9885ffdbb38bc5964762e))

- Block report coverage omission
  ([`1b6df51`](https://github.com/lowRISC/dvsim/commit/1b6df51a82c1482f26d51cc21e2afc3cc5226431))

- Incorrect result model with `---map-full-testplan`
  ([`b29bd6a`](https://github.com/lowRISC/dvsim/commit/b29bd6af88f3da82bd4ff21d25034f071e82fe6c))

- Make report stage table accordion & error buckets optional
  ([`7df2902`](https://github.com/lowRISC/dvsim/commit/7df290289d126f12793455b2556ec28f37310d7a))

- Stop auto-collapsing accordion in block HTML report
  ([`cb6e158`](https://github.com/lowRISC/dvsim/commit/cb6e1585ebfbd7a0d19030886ff0bf3b0ae34dbf))

- Use variant name in HTML reports
  ([`8872455`](https://github.com/lowRISC/dvsim/commit/8872455970673d53f4b10019d47f61c6596cd97b))

### Refactoring

- Reduce variant name duplication
  ([`718ca1d`](https://github.com/lowRISC/dvsim/commit/718ca1d2acd8679a03473bcea3c182a7be959db3))


## v1.11.2 (2026-03-05)

### Bug Fixes

- Track error results seen in sim flows
  ([`c75cfe8`](https://github.com/lowRISC/dvsim/commit/c75cfe81dfc407d6f033787d078cd6ae3677cb47))


## v1.11.1 (2026-03-05)

### Refactoring

- Convert status printer to singleton & keep context until end
  ([`4acf367`](https://github.com/lowRISC/dvsim/commit/4acf367c68c34dde9cdbad24a7e04fddee4ead2b))


## v1.11.0 (2026-03-05)

### Features

- Add optional logging to a logfile
  ([`8f5dff8`](https://github.com/lowRISC/dvsim/commit/8f5dff80e935cbe824ed30d845888c500ff0510d))

- Implement logzero functionality directly
  ([`7488f34`](https://github.com/lowRISC/dvsim/commit/7488f348f5307493af8d2a02c610a18881f4a91a))


## v1.10.2 (2026-02-24)

### Refactoring

- Add more scheduler resource instrumentation
  ([`161f13f`](https://github.com/lowRISC/dvsim/commit/161f13f0c5a71dd498eea4ce02f51e228e7ed463))


## v1.10.1 (2026-02-23)

### Bug Fixes

- Add job tool metadata to instrumentation report
  ([`d8d3f52`](https://github.com/lowRISC/dvsim/commit/d8d3f521c1e48bad079117da2a1eb98503ff02e8))

- Remove per-job per-core avg util from resource instrumentation
  ([`a63b91e`](https://github.com/lowRISC/dvsim/commit/a63b91edb008a227531cc7b1aed7105adff69836))


## v1.10.0 (2026-02-18)

### Bug Fixes

- Remove typo in log for requeued jobs
  ([`d64399b`](https://github.com/lowRISC/dvsim/commit/d64399bd421031934372666f576047e37a6fccc1))

### Build System

- Add `psutil` Python dependency
  ([`06f6b73`](https://github.com/lowRISC/dvsim/commit/06f6b734c14a100b9322b086f876a97dca2ccb0d))

### Continuous Integration

- Disable RUF100 unused-noqa check in CI
  ([`c8e6b2f`](https://github.com/lowRISC/dvsim/commit/c8e6b2f94434e193915e82b434c0a0ef2f1b3c0d))

### Features

- Add instrumentation singleton & scheduler hooks
  ([`afbdd38`](https://github.com/lowRISC/dvsim/commit/afbdd383054e7d268c084650c951a5549771c36f))

- Add scheduler instrumentation base classes
  ([`78e9fba`](https://github.com/lowRISC/dvsim/commit/78e9fba2fea02d7c4fd3c6e482bd4049f9c6426f))

- Add scheduler instrumentation CLI argument
  ([`ea883c9`](https://github.com/lowRISC/dvsim/commit/ea883c97850fe76b71f5ddfebba6a85bb31de04b))

- Add scheduler instrumentation for measuring system resources
  ([`e12f7c9`](https://github.com/lowRISC/dvsim/commit/e12f7c9321b96385f86528674590251855d2cdf9))

- Add scheduler timing instrumentation
  ([`3c4553b`](https://github.com/lowRISC/dvsim/commit/3c4553b16eab0a858e882812487c6e3df3728117))


## v1.9.2 (2026-02-17)

### Refactoring

- Add main entry points for main and admin CLIs
  ([`709117f`](https://github.com/lowRISC/dvsim/commit/709117fc362cfe6e17d64132a695a69ac96f1f53))

### Testing

- Add scheduler test for shared job names across targets
  ([`151e6ab`](https://github.com/lowRISC/dvsim/commit/151e6ab07b87349f812b7602c250b1d370f4dd8d))


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
