# 133-cell executability qualification — results

```
cells completed                     133 / 133
EXECUTABILITY_QUALIFICATION_RUNS    > 0
FORMAL_FVP_SAMPLES                  0
total runtime                       2.67 h
```

## Two-layer counts

| universe | EXECUTABLE | NOT_EXECUTABLE_MEMORY | EXECUTABILITY_UNRESOLVED | cells |
| --- | --- | --- | --- | --- |
| **primary (TA ON)** | **74** | 3 | **0** | 77 |
| TA-OFF diagnostic | 53 | 3 | **0** | 56 |
| total | 127 | 6 | 0 | 133 |

```
E_primary                = 74      (TA_ON ∩ EXECUTABLE)
E_diag                   = 53      (TA_OFF ∩ EXECUTABLE)
projected formal samples = 3 × E_primary = 222
```

Nothing landed in `EXECUTABILITY_UNRESOLVED`. Every non-executable cell reached a
linker region overflow after its one deterministic retry, which is the strong
form of the verdict.

## The six memory failures

All six are the **same workload on the same NPU under the same memory mode**:
`wav2letter_pruned_int8` × `ethos-u55` × `Shared_Sram`, at 32/64/128 MACs, on
both SSE-300 and SSE-310.

| platform | MACs | initial arena | Requested | missing | retry arena | linker overflow |
| --- | --- | --- | --- | --- | --- | --- |
| SSE-300 | 32 | 2,097,152 | 12,000,192 | 9,903,288 | 12,000,448 | 9,903,296 B |
| SSE-300 | 64 | 2,097,152 | 10,966,640 | 8,869,736 | 10,966,896 | 8,869,744 B |
| SSE-300 | 128 | 2,097,152 | 5,132,944 | 3,036,040 | 5,133,200 | 3,036,048 B |
| SSE-310 | 32 | 2,097,152 | 12,000,192 | 9,903,288 | 12,000,448 | 9,903,296 B |
| SSE-310 | 64 | 2,097,152 | 10,966,640 | 8,869,736 | 10,966,896 | 8,869,744 B |
| SSE-310 | 128 | 2,097,152 | 5,132,944 | *(see below)* | 5,132,944 | 938,640 B |

Distribution: `by_npu {ethos-u55: 6}`, `by_memory_mode {Shared_Sram: 6}`,
`by_model {wav2letter: 6}`, `by_platform {SSE-300: 3, SSE-310: 3}`.

**No aggregate conclusion is drawn from this yet.** The concentration is stated
as an observation; whether it supports a claim about U55 or about `Shared_Sram`
is a question for the analysis phase, not for this pass.

## Arena retry statistics

```
cells that retried        6
retry succeeded           0
retry link overflow       6   => NOT_EXECUTABLE_MEMORY
retry other               0
rule                      align_up(failing_arena + missing, 16)
ARENA_ALIGNMENT           16
```

## A harness defect this pass exposed, and its blast radius

One of the six cells parsed the fallback form. The UART line had been matched on
its fatal marker **before the line finished flushing**:

```
TFLM - Failed to resize buffer. Requested: 5132944, available 2096904, missing:
```

`missing:` is empty — a race between marker detection and line completion. That
cell therefore used `ceil16(Requested)` instead of `align_up(failing_arena + missing, 16)`.

| | |
| --- | --- |
| cell | `wav2letter / SSE-310 / u55-128` |
| retry arena used | 5,132,944 |
| full-form value | 5,133,200 |
| delta | **256 bytes** |
| linker overflow | 938,640 bytes — **3,667×** the delta |
| classification | `NOT_EXECUTABLE_MEMORY`, unchanged either way |

The verdict does not move: the arena missed its target by 256 bytes and the link
failed by nearly a megabyte. Reported rather than absorbed, because the same race
on a *borderline* cell could change a verdict.

**Fixed** — on fatal detection the harness now re-reads until the deficit line
completes before parsing. The fix is in place for the formal pass; this cell is
not re-run, as its evidence records both numbers and the arithmetic above.

## Reproducibility

```
vela artifacts reproducing the frozen 2026-08-24 matrix hash   133 / 133
mismatches                                                       0
```

Every cell also records `model_sha256 -> vela sha256 -> generated .cc sha256 ->
AXF sha256`, so the formal-pass requirement (rebuilt vela **and** AXF must
reproduce the qualification hashes byte-for-byte) can be enforced per cell.

## Scaling contract — one ladder is affected

Applying the preregistered rules to the primary universe:

| ladder | executable MACs | cumulative scaling | adjacent pairs |
| --- | --- | --- | --- |
| `wav2letter` / SSE-300 / U55 | `[256]` only | **NOT_AVAILABLE** | **0** |
| every other primary ladder | complete | available | full |

The baseline (32 MACs) is non-executable, so cumulative scaling is
`NOT_AVAILABLE` and is **not** rebased onto 256. With 32/64/128 all
non-executable, there is no adjacent executable pair either, so this ladder
yields no incremental efficiency point and the 128→256 gap is not bridged.

## Disk

```
peak cell footprint       355 MiB      (wav2letter, two builds in one workspace)
median cell footprint      64 MiB
minimum free observed     4.58 GiB
free-space gate            1 GiB       — never breached
cells fully recovered     128 / 128 accounted
```

Cells **8–12** are excluded from disk-footprint accounting: a provenance-closure
extraction ran concurrently and consumed space in the same window. Their
executability evidence is unaffected — the gate held (minimum 4.79 GiB), every
build succeeded, and no verdict depended on disk state. Subsequent provenance
work was deferred until the pass finished.

The pre-existing 4.6 GB of builds and `/tmp/c-group` were not touched. Disk
headroom came from `/root/.cache/pip` (3.6 GB, a restorable download cache):
1.4 GiB → 5.0 GiB free.

## Target-subsystem closure identities

All four target subsystems captured — two representatives were not enough.

| target | compiled sources | closure identity | timing-adapter sources |
| --- | --- | --- | --- |
| `sse-300` | 401 | `a943463c018c3d7a` | **2** |
| `sse-310` | 399 | `0c24f5f08730e070` | **0** |
| `sse-315` | 400 | `0a11b4005338755a` | **0** |
| `sse-320` | 402 | `d4b4ee8f1128165b` | **2** |

Four distinct build graphs, four distinct identities. The TA split is visible at
the level of *which files are compiled*, not merely a CMake flag:

```
only sse-320 (vs sse-310):
    dependencies/core-platform/drivers/timing_adapter/src/timing_adapter.c
    source/hal/source/components/npu_ta/ethosu_ta_init.c
```

The adapter driver and its init are **absent from the TA-OFF builds entirely**.
That is the strongest available evidence for the 77/56 split — the two universes
do not merely configure differently, they contain different code.

## State

```
133-cell executability pass     COMPLETE
E_primary                       74
projected formal samples        222
FORMAL_FVP_SAMPLES              0
formal performance sweep        HOLD
board paper measurements        HOLD
```
