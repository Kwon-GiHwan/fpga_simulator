# Measurement semantics — frozen contract for the paper

What each reported number means, which comparisons are admissible, and which are
refused. Frozen before the main sweep so that no metric acquires its meaning
after the data is in.

## Three kinds of number, never mixed

The paper reports figures from three sources with **different semantics**. They
are named differently on purpose and are not interchangeable.

| kind | source | what it is |
| --- | --- | --- |
| **compiler estimate** | Vela summary CSV | a performance-model prediction |
| **simulated observation** | FVP run | a cycle-model result |
| **physical observation** | MPS4 board | software-visible observation on hardware |

## The admissible metric name

For board and FVP timing of a completion-observation interval:

```
software_visible_completion_observation_cycles
```

The internal name `npu_pmu_window_cycles` may be retained in code, provided the
paper defines the interval explicitly as:

> the interval, in NPU PMU cycles, between the CPU issuing the inference command
> and the CPU **observing** the completion indication in an MMIO register.

Both endpoints are CPU-side events. The interval includes register-visibility
delay and MMIO sampling granularity, and it is bounded below by the sampling
loop's own period.

## Compiler estimates are not measurements

Vela reports `cycles_npu`, `cycles_sram_access`, `cycles_dram_access`,
`cycles_total`, `inference_time` and `inferences_per_second`.

`inference_time = cycles_total / core_clock`, with `core_clock` a **system-config
assumption** (1.0 GHz in the default configuration observed), not a measured
frequency. These are named `vela_estimated_*` throughout and are never presented
on the same axis as an observation without being labelled as estimates.

## Forbidden interpretations

Frozen. These are refused in code where the analyzer can see them, and are
prohibited in prose regardless.

```
NPU execution latency
internal completion latency
internal completion timestamp
T_npu
QREAD is N cycles faster/slower than STATUS
cross-variant absolute cycle difference or ratio
```

The specific arithmetic that is refused: V14 Q floor 732 and V15 S5 floor 754 may
not be subtracted or divided (`RULE_CROSS_VARIANT_ABSOLUTE_COMPARISON`).

Vocabulary refused by the analyzer's guard: `latency`, `t_npu`, `faster`,
`slower`, `internal completion`, `npu completion`, `execution time`,
`cycles later than`, `cycles earlier than`, `cycles behind`, `cycles ahead of`.

## Admissible comparisons

| comparison | admissible | basis |
| --- | --- | --- |
| within-configuration repeatability | **yes, numeric** | same metric, same config, same platform |
| within-variant MAC scaling | **yes, numeric** | one platform, one NPU generation, config varied |
| Vela estimate vs Vela estimate | **yes, numeric** | same model, same semantics |
| FVP vs FVP, same generation | **yes, numeric** | same simulator semantics |
| qualitative structure across matched controls | **yes, qualitative only** | V15 precedent |
| **FVP vs board, absolute cycles** | **NO** | timing domains not shown comparable |
| **FVP vs board, ranking / trend** | **yes, qualitative** | see below |
| **across FVP generations, absolute** | **conditional** | see the version-skew caveat |
| Vela estimate vs any observation, absolute | **NO** | prediction vs observation |

### FVP-versus-board

Numeric equality is **not** required and is not claimed. The two are not shown to
share a timing domain: the FVP is a cycle model, the board is an FPGA
prototyping platform at its own clock, and the board metric is a CPU observation
carrying sampling granularity that the simulator need not reproduce.

Admissible validation criteria are ranking preservation, scaling-trend
preservation, bottleneck consistency, repeatability, and the **direction and
magnitude of deviation** reported as a characterization of the gap rather than
as agreement or disagreement.

### Across FVP generations — a real confound

The installed FVPs are **different Fast Models versions**:

| FVP | Fast Models |
| --- | --- |
| SSE-300 (U55, U65) | 11.22.35, Aug 2023 |
| SSE-310 / SSE-310_U65 | 11.24.13, Jan 2024 |
| SSE-320 (U85) | 11.27.25, Sep 2024 |
| SSE-315 (AVH, U65) | 11.31.28, Mar 2026 |

Cross-generation absolute cycle comparison therefore confounds **NPU generation**
with **simulator version**. Two options, to be chosen before the sweep:

1. **Qualitative cross-generation only** — report trends and scaling, not
   absolute cross-generation deltas. Requires no new tooling.
2. **Version-matched subset** — obtain one Fast Models version covering all
   required generations, and treat cross-generation absolute numbers as valid
   only within that matched set.

Until one is chosen, cross-generation absolute cycle claims are **UNPROVEN**.

### The `--fast` caveat

`FVP_Corstone_SSE-315` exposes `ethosu.extra_args=--fast`, documented as: *"In
fast mode, NPU performance counters are not representative of counters on real
hardware."*

Fast mode is **prohibited** for any run producing a reported number.
`FVP_Corstone_SSE-320`'s `extra_args` is documented as "reserved for future use"
and must be left empty. Every run records the value it used.

## Invalid-run handling

Inherited from the board campaigns: a run is valid or it is discarded with a
named reason. Invalid runs are never down-weighted into a distribution, and a
short cell is not a cell. Reproduction floors are per-configuration minima;
pooling before classification is prohibited.
