# Formal FVP analysis plan — frozen before the analyzer reads a cycle value

Input is `paper-fvp-formal-evidence-frozen` (`2dd77839432ac22c…`), which is
**never modified**. This plan and the analyzer contract are frozen first, then
applied exactly once.

## Canonical cell value

```
require  M1 == M2 == M3      (all 19 equality-bearing fields)
then     canonical_formal_value = M1
```

The repetitions are **not** averaged. They are byte-identical, so a mean or
median would add no information and would misrepresent deterministic repetitions
as a statistical sample. `M1` is the representative value; `M2`/`M3` are
determinism qualification evidence.

An input where `M1 != M2 != M3` is **rejected**, not summarised.

## Scaling — within platform × NPU × workload only

For a preregistered MAC ladder `M0 < M1 < … < Mi`:

```
speedup(Mi)                  = cycles(M0) / cycles(Mi)
cumulative_efficiency(Mi)    = speedup(Mi) / (Mi / M0)
incremental_efficiency(Mi-1 -> Mi)
                             = (cycles(Mi-1) / cycles(Mi)) / (Mi / Mi-1)
```

Classification, threshold fixed and never revisited:

```
incremental_efficiency >= 0.75          STRONG
0.50 <= incremental_efficiency < 0.75   PARTIAL
incremental_efficiency <  0.50          WEAK_OR_SATURATED
```

Saturation point = the **first** `Mi` whose `incremental_efficiency < 0.50`;
if none, `NONE_OBSERVED`.

Preregistered ladders:

| platform / NPU | ladder |
| --- | --- |
| SSE-300 / ethos-u55 | 32, 64, 128, 256 |
| SSE-300 / ethos-u65 | 256, 512 |
| SSE-320 / ethos-u85 | 128, 256, 512, 1024, 2048 |

## Executability gaps

If the preregistered baseline `M0` is non-executable:

```
cumulative scaling   NOT_AVAILABLE
saturation           NOT_AVAILABLE
```

The baseline is **never** rebased onto a higher MAC. Incremental efficiency is
computed only between two *adjacent preregistered* MAC points that are **both**
executable; a non-executable point is never bridged.

Known affected ladder: `wav2letter / SSE-300 / ethos-u55` — non-executable at
32/64/128, executable at 256. It therefore yields cumulative `NOT_AVAILABLE`,
**0** incremental points, and saturation `NOT_AVAILABLE`. Neither `32→256` nor
`128→256` is constructed as a step.

## Workload ranking

Per valid configuration, rank the 7 workloads by canonical `M1` cycles.

Cross-configuration comparison is **ordinal only** — Spearman `rho`, which does
not assume a shared absolute cycle axis. Rank correlation is computed **only over
the workload subset executable in both configurations**; a partial ladder is
never padded to 7.

## Vela ↔ FVP — trend agreement, not absolute error

Prohibited: `FVP − Vela` absolute error, `FVP / Vela` read as a calibrated
latency ratio, and any statement of the form "Vela underestimates by X cycles".

Each series is normalised independently within the same platform × NPU ×
workload ladder, and only the *shape* is compared:

```
Vela speedup vs MAC          <->  FVP speedup vs MAC
Vela incremental efficiency  <->  FVP incremental efficiency
Vela saturation class/point  <->  FVP saturation class/point
rank agreement
```

The question is how well the compiler estimate predicts **scaling behaviour**,
never absolute cycle fidelity.

## PMU — generation-local

Cross-generation comparison is admitted **only** for events verified
`COMMON_SEMANTICS`:

```
CYCLE
NPU_IDLE
CC_STALLED_ON_BLOCKDEP
```

`NPU_ACTIVE` and the `AXI*` / `EXT*` / `SRAM*` families are **not** assumed to
share semantics across generations. U55/U65 AXI-family counters are analysed
within their generation; U85 EXT/SRAM-family counters within U85. The primary
cross-generation view of memory behaviour stays with Vela estimates.

## Standing prohibitions

```
no cross-generation raw absolute-cycle comparison
no TA-OFF cells in primary performance analysis
no scaling across a non-executable MAC gap
no rebasing when the preregistered baseline is non-executable
no FVP-vs-board absolute-cycle equality
no cross-generation PMU comparison outside COMMON_SEMANTICS
no absolute Vela-vs-FVP latency or error interpretation
```

## Outputs

```
docs/paper/analysis/
  canonical_cells.csv
  executability.csv
  scaling.csv
  saturation.csv
  workload_ranking.csv
  vela_fvp_trend_agreement.csv
  pmu_within_generation.csv
  analysis_meta.json
```

## Order of work

```
contract + code complete
  -> synthetic / mutation tests (every prohibition must actually reject)
  -> paper-fvp-analysis-plan-anchor
  -> analyzer applied ONCE to the frozen 222-sample evidence
  -> derived tables
  -> results evidence freeze
  -> STOP
```

No scientific narrative and no causal interpretation at this stage. Numbers are
computed; what they mean about any architecture is deferred.
