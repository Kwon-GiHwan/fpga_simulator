# U85 per-layer profiling path — P0-A-B audit

Audited 2026-09-02 from `/workspace/per-layer-profiling/` in `benchmark-runner`
(the prior study's working tooling; refined variants of the exploratory copies
under `/tmp/per-layer-profiling/`). No measurement was run.

## Prior methodology, as implemented

### Vela insertion point (`patch-vela.py`, 85 lines)

- Target file:
  `/usr/local/lib/python3.10/dist-packages/ethosu/vela/register_command_stream_generator.py`
- Anchor: immediately after `generate_operation_code(emit, npu_op)`; uniqueness
  double-checked against the following `if add_to_debug_db` line.
- Inserted behaviour: when env `ETHOSU_PER_LAYER_PROFILING=1` at Vela compile
  time, emit `cmd0.NPU_OP_IRQ` with `param=op_index` after every block
  operation, **skipping `NpuDmaOperation`**.
- Reversible: backup + `--revert`. A sparse variant (`patch-vela-sparse.py`)
  emits the IRQ after every N-th op (`STEP=2` documented: merged pairs
  `[c0+c1, c2+c3, …]`).

### Command-stream consequence

The generated `.tflite` command stream carries `NPU_OP_IRQ(op_index)` between
operations. The NPU halts at each IRQ until the CPU clears it, which is what
makes the PMU snapshot stable.

### Driver handler (`patch-driver.py`, 204 lines)

- Target: `dependencies/core-driver/src/ethosu_driver.c` (backup + revert).
- Mid-stream IRQ (`cmd_end_reached == 0`):
  1. snapshot PMU (NPU halted → stable),
  2. reset PMU counters for the next operator,
  3. clear IRQ (NPU resumes),
  4. return **without** signalling the completion semaphore.
- `NPU_OP_STOP` (`cmd_end_reached == 1`): normal completion path.
- Record: `PROFILING_MAX_LAYERS = 256` static entries of
  `{uint64 total_ccnt, uint32 active, uint32 evt_cnt1..3}`; printed after the
  run as CSV lines `Layer,TotalCycles,ActiveCycles,EvtCnt1,EvtCnt2,EvtCnt3`
  via `LOG_INFO` (UART).

### PMU delta semantics

Snapshot-then-reset per layer: each row is a per-operator absolute count since
the previous reset, not a cumulative delta computed on the host. Whole-model
coherence (sum of rows vs clean run) is exactly the P0-C item 6 check.

### Supporting harness

- `test-determinism.sh` — builds profiled and clean
  `mlek_inference_runner.axf` from the same model, runs each multiple times,
  diffs per-layer vectors, and prints an explicit
  identical-vs-"statistical reporting needed" verdict. This matches the P0-D
  repetition-semantics requirement and can be ported nearly as-is.
- `batch-8.1-baseline-validation.sh`, `batch-8.2-chunk-boundary.sh` — chunk
  boundary experiments (dense vs sparse IRQ placement).
- `exp-a-stall-profiling.sh` — swaps the stock profiler's beat events for
  stall/MAC events via `sed` on `ethosu_profiler.c` (origin of the
  `.bak.stall` backup; currently reverted — tree matches stock).

## What is established vs NOT established for U85

| item | status |
| --- | --- |
| Vela insertion point exists and is anchored | ESTABLISHED (source read) |
| IRQ placement semantics (skip DMA, param=op_index) | ESTABLISHED (source read) |
| Driver IRQ handler + snapshot/reset semantics | ESTABLISHED (source read) |
| Max operations safely profiled | 256 (static buffer). `param` width for `op_index` in `cmd0` NOT verified against the U85 command-stream spec — verify before trusting op_index > 8-bit/16-bit boundaries |
| Prior runs on U85 | **NONE FOUND.** All recorded artifacts are U55 (`ETHOS_U_NPU_CONFIG_ID=H256`, `Ethos_U55_High_End_Embedded` summary CSVs) |
| `NPU_OP_IRQ` validity in the U85 command stream / Vela 5.0.0 U85 backend | **NOT ESTABLISHED** — the patch was written against the U55/U65 path; whether the U85 register command stream generator flows through the same anchor and accepts `cmd0.NPU_OP_IRQ` must be proven at P0-C |
| FVP_Corstone_SSE-320 IRQ behaviour under mid-stream halts | **NOT ESTABLISHED** (no FVP IRQ limitation was found documented in the tooling; absence of evidence only) |
| Old "15 operations then merge" rule | **NOT re-established.** Nothing in the audited tooling encodes 15; the sparse STEP mechanism exists instead. Per the plan, the chunk rule (if any) must be derived from the current U85 path, not assumed |
| Perturbation figure | prior "≤3.5 %" claim NOT applicable to U85; measure directly at P0-C |

## Port plan implications (for P0-B/C)

1. The patch pair applies to the shared Vela install and the shared
   core-driver — both are also inputs to frozen work. Therefore: apply patches
   only inside a **dedicated build/run namespace**, verify `--revert`
   round-trip hashes, and never rebuild any frozen-tagged artifact while
   patches are applied. (The driver patch defines
   `ETHOSU_PER_LAYER_PROFILING 1` unconditionally when applied — build clean
   and profiled AXFs in separate sessions, or gate it, and record patch
   identity hashes per artifact.)
2. Profiled evt slots today capture only 3 of the 5 stock events per layer
   (`evt_cnt1..3`). For U85, decide at P0-B which qualified events occupy the
   per-layer record; hardware allows 8 event counters, the record struct is
   patch-controlled.
3. Determinism check (`test-determinism.sh` pattern) runs BEFORE the formal
   repetition contract is chosen — as the plan requires.
