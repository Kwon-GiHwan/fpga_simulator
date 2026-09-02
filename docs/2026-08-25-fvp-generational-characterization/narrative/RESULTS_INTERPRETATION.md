# Results interpretation

Source: `paper-fvp-analysis-results-frozen` (`11be18ef242678b2…`). No new metric,
threshold, correlation, or regrouping is introduced here.

Each statement is tagged **OBSERVED**, **SUPPORTED INTERPRETATION**, or
**NOT ESTABLISHED**.

---

## 1. Within-platform MAC scaling

**OBSERVED.** Across 21 preregistered ladders (platform × NPU × workload) on
TA-enabled configurations, 53 adjacent MAC transitions were evaluable:

| incremental class | count |
| --- | --- |
| `STRONG` (≥ 0.75) | 28 |
| `PARTIAL` (0.50–0.75) | 23 |
| `WEAK_OR_SATURATED` (< 0.50) | 2 |
| `NOT_AVAILABLE` (adjacent point non-executable) | 3 |

**OBSERVED.** Under the preregistered saturation criterion (first transition with
incremental efficiency strictly below 0.50):

```
NONE_OBSERVED    19 / 21
saturation        1        SSE-320 / ethos-u85 / rnnoise_INT8 at MAC 512
NOT_AVAILABLE     1        wav2letter / SSE-300 / ethos-u55
```

**SUPPORTED INTERPRETATION.** Across the tested TA-enabled configurations, most
workload/platform ladders retained at least partial scaling over the explored MAC
range. No saturation point was observed in 19 of 21 ladders; one U85/`rnnoise`
ladder crossed the threshold, and one U55/`wav2letter` ladder was not evaluable
because its lower-MAC configurations were not executable.

**SUPPORTED INTERPRETATION.** Scaling response remained workload-dependent rather
than following a single universal saturation point — the 53 transitions are
distributed across `STRONG` and `PARTIAL`, and only one ladder crossed the
threshold.

**NOT ESTABLISHED.** That these workloads *do not saturate*. `NONE_OBSERVED`
means no saturation was seen **within the tested MAC range**, not that none
exists. Nothing here extends to MAC configurations beyond those measured.

**NOT ESTABLISHED.** That scaling is "mostly linear". `STRONG` is a threshold at
≥ 0.75 efficiency, not ideal scaling; 28 of 53 meeting it does not make the
majority linear.

**NOT ESTABLISHED.** Any compute-bound or memory-bound explanation for the
observed distribution. No operator-level or PMU evidence supporting such a
mechanism was collected.

---

## 2. Vela estimates versus FVP

**OBSERVED.** Over 20 comparable ladders, each series normalised independently:

```
saturation classification agreement    19 / 20
normalised speedup rank agreement      19 / 20   (Spearman rho == 1.0)
per-step incremental class agreement   highly variable
                                       (4/4, 3/4, 2/4, 3/3, 2/3, 1/3, 1/1, 0/1 all occur)
```

**SUPPORTED INTERPRETATION.** Vela generally preserved the coarse scaling
structure observed under FVP — particularly the ordering of normalised speedups
and the presence or absence of saturation — but was less reliable at reproducing
the exact scaling class of individual MAC transitions.

**SUPPORTED INTERPRETATION.** Compiler estimates are more dependable for broad
trend prediction than for fine-grained step behaviour.

**NOT ESTABLISHED.** That Vela predicts FVP cycles accurately, that it carries a
quantifiable error percentage, or that it systematically over- or under-estimates
FVP. No absolute error, ratio, or calibration was computed, and the analysis
contract rejects such a metric outright.

---

## 3. Workload ranking stability

**OBSERVED.** Over 55 configuration pairs, ranking workloads by canonical cycles:

```
Spearman rho == 1.0     31 / 55
rho minimum             0.9429
rho median              1.0000
pairs over 7 shared workloads   28
pairs over 6 shared workloads   27
```

The 27 six-workload pairs involve `SSE-300 / ethos-u55`, where `wav2letter` is
not executable. Correlation was computed only over the shared executable subset.

**SUPPORTED INTERPRETATION.** Workload ordering was highly stable across
configurations. Relative workload cost is preserved far more strongly than any
absolute quantity, which makes ordinal comparison the appropriate cross-platform
instrument for this dataset.

**NOT ESTABLISHED.** Any claim requiring a shared absolute cycle axis. Spearman
`rho` is used precisely because it assumes none.

---

## 4. Executability as a first-class result

**OBSERVED.** Of the 133-cell capability universe, 6 cells were
`NOT_EXECUTABLE_MEMORY`, and they are homogeneous:

```
workload      wav2letter_pruned_int8   (6/6)
NPU           ethos-u55                (6/6)
memory mode   Shared_Sram              (6/6)
MAC           32, 64, 128
platform      SSE-300 (3), SSE-310 (3)
```

Each reached a linker SRAM region overflow after the single deterministic arena
retry. `EXECUTABILITY_UNRESOLVED` was 0.

**SUPPORTED INTERPRETATION.** Executability itself became a limiting factor for
the largest workload. Six `wav2letter` / U55 / `Shared_Sram` configurations could
not accommodate the deterministically required activation arena within the mapped
SRAM, despite successful Vela compilation.

**SUPPORTED INTERPRETATION.** Compiler acceptance alone does not establish
deployability on a concrete platform memory map. All 133 cells compiled; 6 could
not run.

**Classification: SYSTEM-LEVEL MEMORY / DEPLOYABILITY LIMITATION** — not a pure
NPU microarchitecture limit.

**NOT ESTABLISHED.** That U55 cannot support large models, that U55 has
insufficient memory, or that low MAC counts cause memory exhaustion. MAC count,
NPU generation, memory mode, and the platform memory map are confounded in these
six cells, and the cause cannot be attributed to U55 architecture alone.

---

## Research questions

**RQ1 — generational / platform performance characteristics.**
*SUPPORTED:* the generations and configurations differ primarily in their
normalised scaling behaviour, workload ordering, and deployability
characteristics, rather than in directly comparable absolute FVP cycle values.
*NOT ESTABLISHED:* any "U85 is faster than U55" statement. Fast Models version
skew and timing-adapter differences make absolute cross-generation comparison
unsupportable on this data.

**RQ2 — MAC scaling and saturation.**
*SUPPORTED:* most tested workload/platform ladders continued to benefit from
additional MAC resources over the explored range. Only one ladder crossed the
preregistered saturation threshold, while most adjacent transitions remained in
the strong or partial regimes. Scaling response was workload-dependent rather
than converging on a single universal saturation point.

**RQ3 — board validation. `PENDING_VALIDATION`.**
Not answered by this dataset. The expectation framework is unchanged: compare
workload ranking, relative workload cost, repeatability, and qualitative
bottleneck consistency; do **not** compare absolute FVP-versus-board cycles or
MAC scaling.

This interpretation is frozen **before** any board result exists. Board findings
may fill in RQ3; they do not retroactively revise the FVP interpretation above.

---

## Central paragraph

Across the TA-enabled FVP configurations, most workloads continued to obtain
measurable benefit from increasing MAC resources: 19 of 21 scaling ladders showed
no saturation under the preregistered threshold within the tested range. Vela
largely preserved these coarse scaling trends, matching the FVP saturation
classification in 19 of 20 comparable ladders and preserving normalised speedup
ordering in 19 of 20. Agreement was weaker for individual MAC-to-MAC scaling
classes, indicating that compiler estimates are more reliable for broad trend
prediction than for fine-grained step behaviour. Workload ordering itself
remained highly stable across configurations, while the largest `wav2letter`
workload exposed a separate system-level constraint: several U55 / `Shared_Sram`
configurations compiled successfully but could not fit the required runtime arena
into the platform SRAM.
