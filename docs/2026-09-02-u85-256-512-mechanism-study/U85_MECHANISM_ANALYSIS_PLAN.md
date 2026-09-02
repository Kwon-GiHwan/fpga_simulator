# U85 256→512 mechanism study — preregistered analysis plan (P0-B)

Frozen BEFORE any new 256/512 per-layer or clean measurement is examined.
Amendments after the first formal sample invalidate the affected analysis.
Wording contract: `ASSOCIATED_WITH` / `CONSISTENT_WITH` / `NOT_SEPARATED` /
`NOT_EVALUABLE` wherever causal separation is unavailable.

## 0. Registered manager decisions (2026-09-02, before any data)

| # | decision | choice |
| --- | --- | --- |
| D1 | reversal-group basis | **No preregistered group labels.** All main-track workloads are measured identically; groups are DERIVED from the new P0-D clean whole-model observations by the direction rule in §4. The prior-study premise ("VWW/OD regress") is recorded as motivation only and grants no analytic status. |
| D2 | 256→512 system-config binding | **Dual binding.** B-frozen reproduces the frozen convention (256→`Ethos_U85_SYS_DRAM_Low`, 512→`Ethos_U85_SYS_DRAM_Mid_512`); B-held holds `Ethos_U85_SYS_DRAM_Low` for both MACs. Holding at `Low` makes the 256 build shared between bindings (identical Vela invocation), so each workload has **three distinct Vela artifacts**: `256@Low` (shared), `512@Mid_512`, `512@Low`. This is a registered expansion of the original 12-cell cap, approved by the manager in the D2 selection. |
| D3 | DNN-S | **Admitted on a separate track** (`dnn_s_quantized`, 9.5 % CPU operators). Never pooled with main-track workloads; reported separately; per-layer matching for its CPU-fallback ops follows §7's NPU-op-only rule. |

## 1. Workload identities (exact; no substitution)

| track | workload | model SHA-256 |
| --- | --- | --- |
| main | `rnnoise_INT8` | `9c582545b7c13af44616c44b654f4fe721aa2585630b0ca173ca3589f6f11c2c` |
| main | `vww4_128_128_INT8` | `5e76364e80c45776b735563679d45f611cab7ce7fef2ec4e2db088afe009ccae` |
| main | `yolo-fastest_192_face_v4` | `e94bcdb011784bead70ab0c0e9d2dae1a9ea5f103b43e1e6fac3019302cf71ab` |
| main | `kws_micronet_m` | `c1feed3af5dac44de7477fb4161670ba18a3fc06039e4a14da41b1c4dd454cb4` |
| main | `ad_medium_int8` | `a8b1c9037c2a80e6ff770f0a550777cf744a52850bed6545b2bfc9bacf604c98` |
| separate | `dnn_s_quantized` | `b34dea022996706a558f14fbc967631889cbc82b93f25d326c581763aed71f0b` |

Main-track SHAs are the frozen `canonical_cells.csv` values; a mismatch at
build time is a STOP. `mobilenet_v2` and `wav2letter` are excluded (≤6 cap).

## 2. Formal matrix

```
6 workloads × 3 artifacts (256@Low shared, 512@Mid_512, 512@Low) = 18 cells
each cell: clean whole-model observation + profiled per-layer observation
platform  FVP_Corstone_SSE-320, TA ON, extra_args empty (recorded)
memory    Dedicated_Sram; Vela --optimise Performance --config default_vela.ini
build     SOURCE_DATE_EPOCH=1776763519 contract; mechanism-namespace paths only
```

No other MAC, memory mode, or workload may be added under this plan.

## 3. Questions

- **Q1** Which operators account for the whole-model cycle change over
  256→512 (per binding)?
- **Q2** For operators whose cycles increase, which compiler-visible fields
  change simultaneously (OFM ublock, block config, tile/stripe decomposition,
  scheduling/pass structure, memory placement, Vela estimated cycles)?
- **Q3** What runtime PMU changes accompany those operators? Qualified event
  set only (§6).
- **Q4** Do workloads classified REGRESSING (§4) share one pattern or exhibit
  distinct signatures?
- **Q5** How do workloads classified IMPROVING differ from REGRESSING ones at
  the same boundary?
- **Q6 (from D2)** Does the whole-model direction and its operator
  decomposition differ between B-frozen and B-held — i.e. is the observed
  boundary behaviour `ASSOCIATED_WITH` the system-config discontinuity, the
  MAC change, or `NOT_SEPARATED`?

## 4. Direction classification rule (preregistered; no thresholds)

For each workload and each binding b ∈ {B-frozen, B-held}:

```
delta(b) = clean_cycles_512(b) − clean_cycles_256      (shared 256 artifact)
REGRESSING(b)  iff delta(b) > 0
IMPROVING(b)   iff delta(b) < 0
UNCHANGED(b)   iff delta(b) = 0
```

Group membership for Q4/Q5 uses the B-frozen classification; B-held
classification feeds Q6 only. No magnitude threshold exists; "large" is not a
category.

## 5. Compiler-side transition fields (independent booleans; never collapsed)

Per matched operation, per binding pair: `UBLOCK_CHANGED`,
`BLOCK_CONFIG_CHANGED`, `TILE_GEOMETRY_CHANGED`, `MEMORY_PLACEMENT_CHANGED`,
`COMMAND_OR_PASS_STRUCTURE_CHANGED` — each derived from
`--verbose-performance`/`--verbose-schedule` captures archived per artifact.
A field whose source data is absent for an op is `NOT_EVALUABLE`, never
false.

## 6. Qualified runtime PMU set

Only events classified VERIFIED_AVAILABLE by the P0-A audit:

```
ETHOSU_PMU_CYCLE (CCNT)          per-op TotalCycles
ETHOSU_PMU_NPU_ACTIVE            per-op active
SRAM_RD/WR_DATA_BEAT_*           per-op sram beats
EXT_RD/WR_DATA_BEAT_*            per-op ext beats
```

The per-layer record struct is extended (patch-controlled) from 3 to 5 event
slots so all four beat events are captured alongside NPU_ACTIVE. Stall-family
events remain SEMANTICS_UNVERIFIED and are **excluded from analysis fields**;
if recorded at all they are exploratory appendix data, named as such. No
U55/U65 AXI mapping may be fabricated; raw evidence uses U85 native names.

## 7. Operator identity and matching

- Stable operation identity = (workload, Vela op_index from the IRQ `param`,
  op type, IFM/OFM shape) as emitted by the profiled command stream and the
  Vela schedule capture; join across artifacts by identity, never row order.
- DNN-S CPU-fallback operators are outside the NPU command stream; matching
  covers NPU ops only, and the uncovered remainder is reported as a declared
  limitation of the separate track.
- Analyzer rejection rules (fail-closed): missing operation, duplicate
  identity, reordered unmatched operations, model SHA mismatch, wrong
  workload pairing, incomplete PMU record, wrong memory/system baseline,
  wrong profiling patch identity, changed Vela/MLEK/driver/FVP identity.

## 8. Repetition semantics (procedure registered; contract deferred to data-free check)

Before formal acquisition, a prequalification determinism check runs the
profiled path ≥3 fresh FVP processes on one representative artifact:
- exact equality of the full metric vector → the formal contract is 3 fresh
  runs with exact equality (the FVP convention);
- deterministic instrumentation offsets with exact repeated vectors →
  documented, same contract;
- anything else → **STOP**; no averaging/tolerance rule may be invented.

## 9. Perturbation

Clean vs profiled whole-model difference is reported descriptively per cell.
No pass/fail threshold exists and none may be added after results. The prior
"≤3.5 %" figure is prior-study context only.

## 10. Prohibited

Absolute Board↔FVP comparisons; causal claims ("ublock causes", "Vela
causes", "memory bandwidth causes", "core replication superior");
cross-generation event-ID equivalence; merging any of this data into the
frozen formal datasets; latency/T_npu vocabulary for observation intervals.

## 11. Outputs and freeze sequence

```
U85_PROFILING_QUALIFICATION.md          (P0-C; tag paper-u85-layer-profiling-qualified)
U85_FORMAL_MATRIX.csv                   (P0-D raw index; hashed evidence tree)
U85_OPERATOR_MATCH.csv
U85_256_512_DIFFERENTIAL.csv
U85_MECHANISM_RESULTS.md                (computed, not interpreted)
U85_MECHANISM_LIMITATIONS.md
U85_MECHANISM_META.json
```

Freeze order: capability audit (done, `145f36d`) → this plan
(`paper-u85-mechanism-plan-anchor`) → profiling qualification → formal raw
evidence → derived results → STOP for manager review. No final narrative.
