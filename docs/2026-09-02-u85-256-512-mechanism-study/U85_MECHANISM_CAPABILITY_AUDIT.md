# U85 mechanism study — P0-A capability audit

Audited: 2026-09-02. Scope: source/configuration authority only; no formal
measurements were taken. Everything below was read from the pinned stack on
`gihwan:/` and container `benchmark-runner` (image `fpga-simulator:latest`,
up since 2026-08), or from frozen evidence in this repository.

## Audited stack identity

| component | identity | authority |
| --- | --- | --- |
| MLEK | `26.03-8-gb2c0bb2` (matches frozen source closure) | `git describe` in `/opt/arm/ml-embedded-evaluation-kit` |
| MLEK tracked state | clean — dirty entries are untracked `.bak.*` backups and build leftovers only; every `.bak` compared byte-identical to its current file | `git status --porcelain` + `diff` (profiler, UseCaseHandler, platform_drivers, ethosu_driver) |
| core-driver | `25.11` @ `0356707` | `git describe` in `dependencies/core-driver` |
| Vela | 5.0.0 at `/usr/local/bin/vela` | `vela --version` |
| FVP | `/home/gihwan/fvp-corstone320-installed/models/Linux64_GCC-9.3/FVP_Corstone_SSE-320` (Fast Models 11.27.25 per frozen record; re-verify at P0-C launch) | filesystem + frozen MEASUREMENT_SEMANTICS |
| U85 builds | `build-prof-u85-{128,256,512,1024,2048}` exist in MLEK root (plus `build-prof-u85-256-new`, unaudited variant — do NOT use without identity check) | `ls` |

## A. U85 PMU capability — summary

Authority: `dependencies/core-driver/include/pmu_ethosu.h`, `ETHOSU85` enum
block (lines 143–318). Mechanically extracted — see
`U85_PMU_EVENT_AUTHORITY.csv` (172 entries: `NO_EVENT`=0, 170 events,
`SENTINEL`=171). No value was derived by hand.

Hardware counters: 48-bit cycle counter (CCNT) + 8 event counters
(vendor board config; the stock profiler uses CCNT + 5 event slots, leaving
3 free).

### Stock profiler exposure (U85 branch of `ethosu_profiler.c`)

| slot | event | frozen-evidence status |
| --- | --- | --- |
| CCNT | `ETHOSU_PMU_CYCLE` | emitted; TOTAL in frozen records |
| CNT1 | `ETHOSU_PMU_NPU_ACTIVE` | emitted; ACTIVE (IDLE derived) |
| CNT2 | `ETHOSU_PMU_SRAM_RD_DATA_BEAT_RECEIVED` | emitted on board; **absent from frozen FVP formal records** (parser of the day) |
| CNT3 | `ETHOSU_PMU_SRAM_WR_DATA_BEAT_WRITTEN` | same |
| CNT4 | `ETHOSU_PMU_EXT_RD_DATA_BEAT_RECEIVED` | same |
| CNT5 | `ETHOSU_PMU_EXT_WR_DATA_BEAT_WRITTEN` | same |

### Requested concept mapping

Classification uses the four P0-A classes. "Semantics documented" fails for
every non-stock event: the header's own caveat is *"These values are symbolic.
Actual HW-values may change. I.e. always use API"*, and no TRM/semantic
document is present in the audited stack. Concepts below therefore cap at
`SEMANTICS_UNVERIFIED` until an Arm U85 TRM authority is added to the audit.

| concept | U85 candidate events (native names) | classification |
| --- | --- | --- |
| TOTAL / ACTIVE / IDLE | `CYCLE`, `NPU_ACTIVE` (+derived idle), `NPU_IDLE` | **VERIFIED_AVAILABLE** |
| SRAM_RD / SRAM_WR / EXT_RD / EXT_WR | the four `*_DATA_BEAT_*` events above | **VERIFIED_AVAILABLE** (emitted on board; FVP re-capture requires the same stock config) |
| read stall | `SRAM_RD_TRAN_REQ_STALLED`, `EXT_RD_TRAN_REQ_STALLED`, `SRAM_RD_STALL_LIMIT`, `EXT_RD_STALL_LIMIT` | SEMANTICS_UNVERIFIED (present in enum; needs slot patch + TRM authority) |
| write stall | `SRAM_WR_TRAN_REQ_STALLED`, `SRAM_WR_DATA_BEAT_STALLED`, `EXT_WR_*` equivalents | SEMANTICS_UNVERIFIED |
| block dependency stall | `CC_STALLED_ON_BLOCKDEP` | SEMANTICS_UNVERIFIED (never configured in any frozen run) |
| MAC-active / compute-active | `MAC_ACTIVE`; stall split `MAC_STALLED_BY_{W,ACC,W_OR_ACC,IB}` | SEMANTICS_UNVERIFIED |
| DMA / memory wait | `AO_STALLED_BY_{BS,OB,AB,CB,...}`, `WD_STALLED*` family (weight/activation pipeline waits) | SEMANTICS_UNVERIFIED |
| bus transaction counts | `SRAM/EXT *_DATA_BEAT_*` (beats, not transactions); transaction-level events not identified by this audit | beats: VERIFIED_AVAILABLE; transactions: NOT_AVAILABLE (none found in enum by this audit) |

Cross-generation note: none of the above was inferred from U55/U65 names or
ordinals. U85 shares only 22 names with U55/U65 and 18 of those differ in
ordinal; every ID in the CSV comes from the U85 block itself.

## B. Per-layer IRQ profiling path

See `U85_LAYER_PROFILING_PATH.md`. Summary: the prior methodology exists in
this container as working tooling (`/workspace/per-layer-profiling/`) but its
recorded runs are **U55-only** (`ETHOS_U_NPU_CONFIG_ID=H256`,
`Ethos_U55_High_End_Embedded` summaries). Insertion point, driver handler,
snapshot semantics, and buffer limits are identified from source; the FVP IRQ
limitation and the old chunk rule are **not re-established** and are P0-C
items.

## C. Vela schedule observability

`vela --help` (5.0.0) confirms `--verbose-performance` and
`--verbose-schedule` (plus `--verbose-all`,
`--verbose-high-level-command-stream`, `--verbose-allocation`). Field coverage
for ublock/block-config/stripe per operator is asserted by flag presence only;
capturing one 256/512 pair and enumerating actual emitted fields is the first
P0-C/P0-B-preparation action (compile-only, no measurement).

## D. Baseline binding

See `U85_BASELINE_BINDING.md`. Two findings that constrain the plan:

1. The frozen sweep's Vela `--system-config` is **MAC-dependent**:
   `Ethos_U85_SYS_DRAM_Low` (clock assumption 500 MHz) for 128/256 vs
   `Ethos_U85_SYS_DRAM_Mid_512` (1 GHz) for 512. The 256→512 boundary in the
   frozen data therefore crosses a compiler system-config discontinuity, not
   only a MAC change. Matching the frozen baseline reproduces this; holding
   system-config fixed departs from it. **Decision required at P0-B; not made
   here.**
2. `dnn_s_quantized` U85 Vela artifacts exist in the container resources
   (`dnn_s_quantized_vela_Z256.tflite` etc.) but the workload is outside the
   frozen 7-workload universe (9.5 % CPU operators). Its admission is a P0-B
   decision; if admitted it cannot be pooled with fully-NPU workloads.

## STOP/GO assessment for P0-A

```
PMU authority                     SUFFICIENT (mechanical CSV; semantics gap declared)
per-layer path authority          SUFFICIENT for design; U85 qualification PENDING (P0-C)
Vela observability                FLAGS PRESENT; field capture pending
baseline binding                  PINNED, with one declared decision point (system-config)
verdict                           GO to P0-B, carrying the three declared decision points
```
