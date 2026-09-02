# Vela matrix — 133 cells materialized, 2026-08-24

7 frozen workloads × 19 verified configurations. **133/133 compiled.**
Provenance for every cell in `vela_matrix.csv`.

| | |
| --- | --- |
| Vela | 5.0.0 |
| elapsed | 72 s for all 133 |
| per-cell record | model + hash, platform, NPU, MAC config, system config, memory mode, full argument vector, output artifact + hash, estimated cycles, memory estimates, CPU/NPU placement, success |

## A parameter error the matrix caught

The first pass produced **56 failures**, all Ethos-U55:

```
ConfigOptionError: Invalid configuration of arena_mem_area=OffChipFlash…
```

Not a platform limitation — my error. I had applied `Dedicated_Sram` uniformly,
and that mode is invalid for the U55 system config, whose arena has no off-chip
area. MLEK's own build logic already encodes the right answer, so the memory mode
is now taken from there rather than chosen:

| NPU | memory mode | source |
| --- | --- | --- |
| U55 | `Shared_Sram` | MLEK `DEFAULT_NPU_MEM_MODE` |
| U65 | `Dedicated_Sram` | MLEK |
| U85 | `Dedicated_Sram` | MLEK |

With that correction: **133/133**. This is precisely what materializing the
matrix before the sweep is for — the same mistake inside a 399-run FVP sweep
would have burned hours and produced a hole in the results.

## Cycle distribution (Vela estimates)

```
cells            133
total cycles     7.983e8
min              31,846        median  894,564        max  112,339,561
```

| NPU | cells | Σ cycles | min | max |
| --- | --- | --- | --- | --- |
| U55 | 56 | 5.800e8 (**72.7 %**) | 108,953 | **112,339,561** |
| U65 | 42 | 1.165e8 | 35,624 | 15,098,431 |
| U85 | 35 | 1.019e8 | 31,846 | 34,994,742 |

**This settles the projection question empirically.** The heaviest cells are
low-MAC **U55**, not U85 — 112.3 M cycles against U85's 34.9 M maximum. U55
alone is 72.7 % of all simulated cycles. The `wav2letter @ U85-1024` point is
nowhere near the worst case, confirming the correction that 12.4 h was never an
upper bound.

## Local runtime calibration — SSE-320 / U85-1024 only

Two measured points on **one** FVP binary at **one** configuration:

| workload | FVP cycles | wall-clock |
| --- | --- | --- |
| `rnnoise_INT8` | 49,086 | 1 s |
| `wav2letter_pruned_int8` | 4,115,068 | 112 s |

```
k     ≈ 2.73e-5 s per simulated cycle
fixed ≈ small; not resolvable — the 1 s reading has 1 s granularity,
        and the fit lands slightly negative, meaning "small", not "below zero"
```

**Local to SSE-320 / U85-1024.** Not generalized to other FVP binaries, Fast
Models versions, or MAC configurations, as directed.

### Vela cycles are not a proxy for FVP cycles

Same cells, both quantities measured:

| workload | Vela estimate | FVP measured | ratio |
| --- | --- | --- | --- |
| `rnnoise` | 33,040 | 49,086 | **1.49** |
| `wav2letter` | 5,761,355 | 4,115,068 | **0.71** |

The disagreement is large **and runs in both directions**. So scaling the Vela
cycle total to predict FVP runtime is unsound, and any projection built on it
carries that uncertainty explicitly.

## Conservative planning range

399 runs (133 cells × 3), using the local `k` and treating the Vela-to-FVP ratio
as the dominant unknown:

| assumption | projected |
| --- | --- |
| FVP cycles = Vela estimate | 18.3 h |
| ratio 0.71 (as `wav2letter`) | 12.8 h |
| ratio 1.49 (as `rnnoise`) | 27.4 h |

**Planning range: roughly 13–28 hours**, with two caveats that could push it
outside:

1. `k` is measured only at U85-1024. Per-cycle simulation speed on the U55 and
   U65 binaries — different Fast Models versions — is **unmeasured**, and U55
   carries 72.7 % of the cycles.
2. The Vela-to-FVP ratio is characterized by two points on one configuration.

This is a planning range, not a validated estimate.
