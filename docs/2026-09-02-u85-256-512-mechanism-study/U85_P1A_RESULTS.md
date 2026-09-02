# P1-A results — memory-configuration robustness (computed, not interpreted)

```
plan      paper-u85-p1a-plan-anchor (1c4f634), applied once
evidence  gihwan:/home/gihwan/mps4/U85_MECH_P1A_20260902T063919Z (EVIDENCE.sha256)
          + frozen P0 clean cells reused for T-DS
runs      16 new cells x 3 fresh FVP runs, all vector-exact; rule failures: 0
```

## Supported tuples / executable cells

- Admitted: T-SO (Sram_Only), T-SH (Shared_Sram), T-DS (Dedicated_Sram =
  P0 baseline, reused). Excluded by audit: Sram_Only × Flash_High
  (**NOT_SUPPORTED** — no U85 Flash system config in the pinned stack).
- **Executable cells: 24/24** (16 new all `OK`; no NOT_COMPILABLE, no
  NOT_EXECUTABLE_MEMORY at link or runtime).

## 256→512 direction per workload × configuration (clean NPU TOTAL)

| workload | mode | 256 | 512 | delta | direction |
| --- | --- | ---: | ---: | ---: | --- |
| rnnoise | Sram_Only | 9,086 | 12,086 | +3,000 | REGRESS |
| rnnoise | Shared_Sram | 31,086 | 46,086 | +15,000 | REGRESS |
| rnnoise | Dedicated_Sram | 36,086 | 55,086 | +19,000 | REGRESS |
| dnn_s | Sram_Only | 7,068 | 9,068 | +2,000 | REGRESS |
| dnn_s | Shared_Sram | 22,068 | 28,068 | +6,000 | REGRESS |
| dnn_s | Dedicated_Sram | 22,068 | 29,068 | +7,000 | REGRESS |
| vww4 | Sram_Only | 262,068 | 179,068 | −83,000 | IMPROVE |
| vww4 | Shared_Sram | 293,068 | 261,068 | −32,000 | IMPROVE |
| vww4 | Dedicated_Sram | 287,068 | 259,068 | −28,000 | IMPROVE |
| yolo | Sram_Only | 792,074 | 504,074 | −288,000 | IMPROVE |
| yolo | Shared_Sram | 812,074 | 568,074 | −244,000 | IMPROVE |
| yolo | Dedicated_Sram | 812,074 | 587,074 | −225,000 | IMPROVE |

- **Configurations reproducing each reversal: all three modes** (rnnoise
  and dnn_s regress under every admitted configuration).
- **Configurations removing a reversal: none.** No configuration creates a
  new reversal either (vww/yolo improve everywhere).
- Magnitude is configuration-sensitive: the rnnoise regression spans
  +3,000 (Sram_Only) to +19,000 (Dedicated_Sram); dnn_s +2,000 to +7,000.
  Reported descriptively; no robustness score is computed (per contract).

## Artifact identity

For every (workload, MAC), the three memory modes produce **three distinct
Vela artifacts** → classification `DIFFERENT_ARTIFACT` for every mode pair
(full SHA-256 table in the evidence `p1a_results.json`). Memory-mode
switching on this stack therefore changes the compiler-generated program as
well as the runtime memory service, and the two contributions are
`NOT_SEPARATED` in these cells — exactly the conflation the contract
required distinguishing, now recorded per cell.

(Contrast, carried from P0: for rnnoise/dnn_s the two 512 *system-config*
bindings produced byte-identical artifacts, so that axis was excluded for
them. The memory-mode axis does not enjoy that invariance anywhere.)

## Answer to the primary question (computed form)

The direction of the U85 256→512 whole-model change **persists across every
admitted memory configuration** for all four workloads; configuration
modulates magnitude only. No configuration turns the operator-level
regressions of vww/yolo (P0-E) into whole-model non-monotonicity, and none
suppresses the rnnoise/dnn_s reversals.

## State

```
P1-A     frozen (this document + evidence root)
P1-B     NOT STARTED (per contract; manager review required)
holds    narrative, interpretation, P2..P4
```
