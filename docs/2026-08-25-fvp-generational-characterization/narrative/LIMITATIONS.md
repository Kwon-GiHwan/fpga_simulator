# Limitations

Constraints that bound what this dataset can support. Several were discovered
during qualification rather than anticipated, and each one narrowed a claim that
had looked available.

## 1. The timing adapter splits the configuration matrix

Only 11 of 19 configurations are benchmarking-valid. MLEK forces
`ETHOS_U_NPU_TIMING_ADAPTER_ENABLED` **off** for `sse-310` and `sse-315`, and
this is visible at the level of *which files are compiled*: the adapter driver
and its init are absent from those builds entirely.

```
sse-300  401 compiled sources, 2 timing-adapter sources
sse-320  402 compiled sources, 2 timing-adapter sources
sse-310  399 compiled sources, 0
sse-315  400 compiled sources, 0
```

With the adapter disabled, memory-system constraints are not modelled. The
observed ~4× difference between SSE-300/U55@32 (112,059 cycles) and
SSE-310/U55@32 (27,059 cycles) is `CAUSE_RESOLVED` — timing adapter ON versus OFF
— and is **a methodology warning, not a performance comparison**. The Vela
artifacts for those two cells are byte-identical, so the NPU command stream is
the same program.

The 56 TA-OFF cells therefore remain executability and diagnostic evidence and
are excluded from performance analysis.

**A claim retracted during this work:** "same NPU across different Corstone
generations" was offered as a clean platform-effect isolation. It is not — the
two sides differ in adapter state, so it compares a memory-constrained model
against an unconstrained one.

## 2. Absolute cross-generation cycle comparison is unsupportable

Fast Models version skew and differing platform configuration confound absolute
cycles across generations. Comparisons are restricted to normalised scaling
behaviour and ordinal workload ranking.

## 3. `SSE-300 / U55@256` versus `U65@256` is not a microarchitecture result

It is the cleanest within-platform pair available — same Corstone, same Fast
Models family, same adapter state, same MAC count — but the memory mode differs
by NPU (`Shared_Sram` for U55, `Dedicated_Sram` for U65), moving the weights
between SRAM and DRAM. It is reportable as a **system-level configuration
comparison** only.

## 4. PMU semantics are generation-conditional

Only `CYCLE`, `NPU_IDLE`, and `CC_STALLED_ON_BLOCKDEP` were verified as
`COMMON_SEMANTICS`. `NPU_ACTIVE` and the `AXI*` / `EXT*` / `SRAM*` families are
not assumed comparable across generations, so cross-generation memory behaviour
is carried by Vela estimates rather than by PMU counters.

Two rules could not be evaluated at all:

| rule | status |
| --- | --- |
| `CC_STALLED_ON_BLOCKDEP` cross-generation | the stock runner never emits this counter |
| U85 `EXT*` / `SRAM*` family | the stock runner emits only AXI-named counters |

These are absences in what the stock runner prints, not analysis failures.
Obtaining them would require modifying the runner, which would break the
stock-runner contract under which every measurement here was taken.

## 5. The inference-count check is weaker than it looks

The stock runner prints `Total number of inferences: 1` as a **hardcoded string
literal** (`UseCaseHandler.cc:158`), not a counter. Requiring `count == 1` is a
valid *completion* check — execution reached post-inference code — but it is not
independent verification of how many inferences ran. With a single-inference
runner the two coincide; the check must not be described as counting.

## 6. Wall-clock is not a performance metric

Host wall-clock was recorded as scheduling evidence only and is excluded from
every equality and performance claim. Simulated metrics are deterministic; host
timing is not.

## 7. Determinism is exact, and that is the point

`M1 == M2 == M3` held on 74/74 cells across all 19 equality-bearing fields. The
repetitions are therefore **not** a statistical sample, and no mean, median, or
confidence interval is reported. `M1` is the canonical value; `M2`/`M3` are
qualification evidence. Reporting dispersion here would manufacture the
appearance of measurement noise where none exists.

## 8. Executability confounds

The six memory failures are homogeneous in workload, NPU, memory mode, and MAC
range simultaneously. That homogeneity prevents attributing the limit to any one
factor. It is recorded as a system-level deployability limitation.

## 9. Scope

Every measurement is FVP-simulated on TA-enabled configurations with a stock
single-inference runner. No board measurement is included; board validation
remains on HOLD and, when opened, is restricted to ranking, relative cost,
repeatability, and qualitative bottleneck consistency.
