# Derived results — computed, not interpreted

```
input        paper-fvp-formal-evidence-frozen   2dd77839432ac22c…
plan         paper-fvp-analysis-plan-anchor     959c473361a71a77…
applied      exactly once
cells         74      formal samples  222
```

Numbers only. No causal or architectural interpretation is offered here.

## Scaling ladders

```
ladders analysed              21
  cumulative AVAILABLE        20
  cumulative NOT_AVAILABLE     1
total incremental points      53
```

The single `NOT_AVAILABLE` is `wav2letter / SSE-300 / ethos-u55`, exactly as
preregistered: its baseline (32 MACs) is non-executable, so cumulative scaling and
saturation are `NOT_AVAILABLE` and it contributes **0** incremental points. It was
not rebased onto 256, and neither `128→256` nor `32→256` was constructed.

Incremental efficiency classes across the 53 computed points:

| class | count |
| --- | --- |
| `STRONG` (≥ 0.75) | 28 |
| `PARTIAL` (0.50–0.75) | 23 |
| `WEAK_OR_SATURATED` (< 0.50) | 2 |
| `NOT_AVAILABLE` (adjacent point non-executable) | 3 |

## Saturation

```
NONE_OBSERVED     19 / 21
observed           1     SSE-320 / ethos-u85 / rnnoise_INT8  at MAC 512
NOT_AVAILABLE      1     wav2letter / SSE-300 / ethos-u55
```

## Vela ↔ FVP trend agreement

Normalised independently per ladder; no absolute error, ratio, or calibration.

```
ladders compared               20
saturation classification agrees   19 / 20
speedup rank agreement rho == 1.0  19 / 20
```

Per-ladder incremental-class agreement is uneven — `4/4`, `3/4`, `2/4`, `3/3`,
`2/3`, `1/3`, `1/1`, `0/1` all occur. Direction and saturation classification
agree far more often than the per-step class does.

## Workload ranking

```
configuration pairs            55
spearman rho == 1.0            31 / 55
rho  min 0.9429   median 1.0000
pairs over 7 shared workloads  28
pairs over 6 shared workloads  27
```

The 27 six-workload pairs are those involving `SSE-300 / ethos-u55`, where
`wav2letter` is not executable. Rank correlation was computed on the shared
executable subset only; no ladder was padded to 7.

## PMU

`pmu_within_generation.csv` carries per-cell counters tagged with their
generation scope. Cross-generation comparison is marked admissible only for
`CYCLE` and `NPU_IDLE`; `NPU_ACTIVE` and the AXI family are recorded but not
declared cross-generation comparable.

## Rules that could not be evaluated

| rule | status |
| --- | --- |
| `CC_STALLED_ON_BLOCKDEP` cross-generation | **not evaluable** — the stock runner's profile block does not emit this counter, so it was never captured |
| U85 `EXT*` / `SRAM*` family | **not evaluable** — the stock runner emits the AXI-named counters only; no EXT/SRAM series present in the UART profile |
| board-vs-FVP relationship | not evaluated — board measurements remain on HOLD |

The first two are gaps in what the stock runner prints, not analysis failures.
Recorded rather than silently dropped, since the PMU audit listed
`CC_STALLED_ON_BLOCKDEP` among the `COMMON_SEMANTICS` events.

## Outputs

```
canonical_cells.csv              74 rows
executability.csv               133 rows
scaling.csv                     scaling rows + incremental steps
saturation.csv                   21 rows
workload_ranking.csv            per-configuration rankings
ranking_preservation.csv         55 pairs
vela_fvp_trend_agreement.csv     20 rows
pmu_within_generation.csv        74 rows
analysis_meta.json
```

## State

```
Analysis                  APPLIED ONCE
Narrative interpretation  NOT STARTED
Board paper measurements  HOLD
```
