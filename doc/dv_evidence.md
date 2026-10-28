<!--
# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
-->
# The `lowrisc-dv-evidence` format

A regression tells you which tests passed.
A verification plan asks a different question: of everything we said we would verify, how much is now backed by something that ran?
Answering it needs the regression's own outcomes in a form a planning tool can read, rather than a log directory and a human.

This is that form.
DVSim writes one of these files per simulation flow, and this page specifies what any producer has to write rather than describing one tool's output.
Anything that can produce it can be scored against a verification plan, whether or not it is DVSim.

## Where DVSim writes it

`<scratch_path>/cov_vplan/dv_evidence.json`, produced by the `cov_vplan` job, and only when the sim config names a `vplan`.
It is written before the annotation step runs and is archived alongside the reports, so it outlives the scratch area it describes.

## Shape

```json
{
  "schema": "lowrisc-dv-evidence",
  "dut": "hmac",
  "tool": "xcelium",
  "produced_by": "dvsim 1.50.1",
  "revision": "https://github.com/lowRISC/opentitan/tree/a1b2c3d (dirty)",
  "timestamp": "2026-08-18T09:00:00+00:00",
  "testcase": {
    "hmac_smoke": [
      { "status": "passed", "seed": 1234, "log": "/scratch/hmac/1234.hmac_smoke/run.log" },
      { "status": "failed", "seed": 5678, "log": "...", "message": "UVM_ERROR", "line": 812 }
    ],
    "hmac_stress_all": [
      { "status": "not_run" }
    ]
  }
}
```

Fields are omitted when they have no value rather than written as `null`.

### Top level

| Key | Meaning |
| --- | --- |
| `schema` | Always `lowrisc-dv-evidence`. Identifies the format to whatever reads the file. |
| `testcase` | Test name to the list of runs of that test. The only required key. |
| `dut` | The design the results are about, named as a verification plan addresses it. |
| `tool` | The simulator that produced them. |
| `produced_by` | What wrote the file, with its version. |
| `revision` | The tree the results were produced against, suffixed ` (dirty)` when it was not clean. |
| `timestamp` | When the run started, as an ISO 8601 datetime with an offset. |

### A run

Every entry under `testcase` is keyed by the test name, because that is the name a plan refers to.
Reseeds of one test share the key and are told apart by `seed`.

| Key | Meaning |
| --- | --- |
| `status` | One of `passed`, `failed`, `killed`, `not_run`. Required. |
| `seed` | The seed the run used, where the flow randomises. |
| `log` | Path to the run's log. |
| `message` | Why it ended that way. Present only on a run that did not pass. |
| `line` | The log line the failure was first reported at. |

`killed` and `not_run` are separate on purpose.
A killed test started and was terminated, so the design was exercised and something went wrong.
A `not_run` test never started, because the scheduler cancelled it once a dependency failed or the run was shut down.
The two are different answers to "did we verify this", and collapsing them would let a build failure read as a passing plan item.

There is no `waived` status.
A waiver needs an owner and a date, and a regression can supply neither, so a known failure is recorded as an inspection instead.

## Inspections

The format also carries an `inspection` key, for claims no simulation can measure, such as a parameterisation or a structural fact.
Those records are written by hand and live in the tree next to the plan they support.
DVSim never produces them; it only passes their path through to whatever consumes this format, so they are out of scope for this document.

## Consumers

[DVPlan](https://github.com/lowRISC/dvplan) reads it to back-annotate a verification plan.
It is not the only thing that could: the format carries no DVPlan concepts, and a dashboard or a CI job wanting machine-readable regression results can read the same file.

## Changing it

The pydantic models in `src/dvsim/report/dv_evidence.py` specify what a producer writes, and this document describes them.
They are not the whole format: the `inspection` half and the rules for scoring a file are the consumer's, and [DVPlan](https://github.com/lowRISC/dvplan) specifies those.
So the models here reject a file carrying an `inspection` key, which is correct, since DVSim writes evidence and never reads it back.
A change to the models or to this document is a change to the format, so change both, and bear in mind that a consumer may be reading files this repo wrote months ago.
