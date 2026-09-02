# U85 256→512 mechanism results — computed, not interpreted

```
inputs   paper-u85-mechanism-formal-evidence-frozen (P0-D, 5ae5f45)
         P0-D2 v3 profiled re-acquisition
         gihwan:/home/gihwan/mps4/U85_MECH_P0D2_20260902T051659Z
plan     paper-u85-mechanism-plan-anchor (a2a4689) + P0-C0 amendment (8971ecd)
analyzer v3.1 (949c532), applied once; group pass (pd_groups.py)
```

Wording per the frozen plan: `ASSOCIATED_WITH` / `CONSISTENT_WITH` /
`NOT_SEPARATED` / `NOT_EVALUABLE`. Numbers only; no causal claim.

## Acquisition summary

| | |
| --- | --- |
| formal cells | 18 (6 workloads × 3 artifacts); profiled arms 15 (dnn_s NOT_AVAILABLE: `shape_signature` fail-closed) |
| repetition | every arm 3 fresh FVP runs, full vector exact-equal (clean 3×18 at P0-D; profiled 3×15 at P0-D2) |
| output identity | profiled CRC == frozen clean CRC on 15/15 cells |
| clean baselines | frozen canonical totals reproduced exactly where a reference exists |
| attribution | one-hot IRQ history windows, ring-decoded; fail-closed contiguity gates all passed |

## Whole-model direction (preregistered rule, clean arms)

| workload | 256@Low | 512@Mid_512 (B-frozen) | 512@Low (B-held) | direction |
| --- | ---: | ---: | ---: | --- |
| rnnoise_INT8 | 36,086 | 55,086 | 55,086 | **REGRESS both bindings** |
| vww4_128_128 | 287,068 | 259,068 | 259,068 | IMPROVE |
| yolo-fastest | 812,074 | 587,074 | 566,074 | IMPROVE |
| kws_micronet | 199,068 | 114,068 | 116,068 | IMPROVE |
| ad_medium | 377,068 | 235,068 | 236,068 | IMPROVE |
| dnn_s (separate track, clean only) | 22,068 | 29,068 | 29,068 | **REGRESS both bindings** |

Q6 (binding sensitivity): for rnnoise and dnn_s the two 512 bindings produce
**byte-identical Vela artifacts** — their regression is invariant to the
system-config choice and is `ASSOCIATED_WITH` the MAC change, not the
compiler system-config. For yolo/kws/ad the bindings differ slightly in
program and cycles (e.g., yolo 587,074 vs 566,074); the boundary's
system-config discontinuity changes those programs but not any direction.

## Q1 — where the cycle change lives

Group-level decomposition (finest common attribution partition; Σgroup
matches whole-model within the constant ISR-boundary residual ±~1k):

| workload (B-frozen) | Σgroup delta | whole-model | groups REG/IMP/SAME |
| --- | ---: | ---: | --- |
| rnnoise | +19,060 | +19,000 | 10 / 1 / 3 |
| vww4 | −29,000 | −28,000 | — |
| yolo | −225,060 | −225,000 | — |
| kws | −84,045 | −85,000 | — |
| ad | −140,970 | −142,000 | — |

**rnnoise's regression is DISTRIBUTED, not concentrated**: the largest group
contributes +4,030 of +19,000; ten groups regress by +1,000..+4,030 each.
Regressing groups are composed of elementwise ops (Add/Mul/Sub/Pack), small
FullyConnected, and Concat/Quantize — per-group increments quantized near
multiples of ~1,000 cycles. Only one group improves (−1,000).

Per-op (separable rows only, B-frozen): kws has **0 regressing ops**; vww
has 19 regressing ops summing +31,015 against improvements of −56,000;
yolo 21 regressing ops (+40,985) against −140,000; ad 2 (+7,000). So
**per-op regressions exist inside net-improving workloads** (vww/yolo) —
an observation `CONSISTENT_WITH` the prior study's premise at op level
while the whole-model direction differs.

## Q2 — compiler-visible transitions co-occurring (separable ops, B-frozen)

| boolean | REGRESS | IMPROVE | SAME |
| --- | --- | --- | --- |
| UBLOCK_CHANGED | 41/43 | 63/65 | 14/16 |
| BLOCK_CONFIG_CHANGED | 27/43 | 60/65 | 11/16 |
| TILE_GEOMETRY_CHANGED | 2/43 | 5/65 | 0/16 |
| MEMORY_PLACEMENT_CHANGED | 0/43 | 0/65 | 0/16 |
| COMMAND_OR_PASS_STRUCTURE_CHANGED | 2/43 | 5/65 | 0/16 |

UBLOCK_CHANGED is near-universal in every direction class — at this
boundary it does not separate regressing from improving ops. A changed
block config is more frequent among improving ops (92%) than regressing
ones (63%). These are co-occurrence counts; the experiment does not
separate hardware geometry from compiler scheduling (`NOT_SEPARATED`).

## Q3 — runtime PMU deltas

Per-op qualified-event sums (ACTIVE, SRAM_RD/WR, EXT_RD/WR) are in
`U85_256_512_DIFFERENTIAL.csv` for separable non-tail ops, and per-unit in
`U85_ATTRIBUTION_UNITS.csv`. Middle-layer EXT_WR is predominantly 0 under
Dedicated_Sram. Stall-family events remain NOT_EVALUABLE (per plan).

## Q4/Q5 — signatures

Workloads classified REGRESSING at whole-model: {rnnoise} (main track) and
{dnn_s} (separate track, clean only). rnnoise's signature: broad small-op
inflation (above). Controls (kws/ad, IMPROVING): kws 0 regressing ops;
ad 2 small DepthwiseConv regressions (+7,000) inside −142,000. vww/yolo
(IMPROVING): substantial minority of regressing convolution ops. Whether
these constitute one pattern or several is left to interpretation; computed
facts only.

## Artifacts

```
U85_FORMAL_MATRIX.csv          18-cell acquisition index (P0-D)
U85_OPERATOR_MATCH.csv         502 matched source-op rows
U85_256_512_DIFFERENTIAL.csv   502 differential rows (booleans, PMU, Vela)
U85_ATTRIBUTION_UNITS.csv      656 lossless attribution units
U85_GROUP_DIFFERENTIAL.csv     315 group rows (common partition)
```

## State

```
P0-E analysis      APPLIED (analyzer v3.1 once + group pass)
interpretation     NOT STARTED (manager review next)
P1..P4, narrative  HOLD
```
