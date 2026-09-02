# Main experiment matrix — proposed, frozen for review

**Not executed.** This fixes what would be run, before any sweep.

Every support claim below is marked with how it was established. Nothing here is
asserted from memory: the failure mode this project has repeatedly hit is a host
declaration treated as authority, so support is taken from the installed tools.

## Verified environment

| | | source |
| --- | --- | --- |
| Vela | 5.0.0 | `vela --version` |
| accelerator configs | u55: 32/64/128/256 · u65: 256/512 · u85: 128/256/512/1024/2048 | `vela --help` |
| board | MPS4 / FI101, Corstone-320, **Ethos-U85 @ 1024 MACs**, 1 NPU | `CFG__NPU0_NUM_MACS 0x400`, `CFG__NUM_NPUS 1`, vendor package |

### Installed FVPs and their stated MAC support

| FVP | NPU | `num_macs` as the model states it | Fast Models |
| --- | --- | --- | --- |
| `SSE-300_Ethos-U55` | U55 | *not stated*, default 128 | 11.22.35 |
| `SSE-300_Ethos-U65` | U65 | *not stated*, default 256 | 11.22.35 |
| `SSE-310` | U55 | "32, 64, 128, or 256" | 11.24.13 |
| `SSE-310_Ethos-U65` | U65 | "256 or 512" | 11.24.13 |
| `SSE-315` (AVH) | U65 | "256 or 512", `[0x100:0x200]` | 11.31.28 |
| `SSE-320` | U85 | `[0x80:0x800]` = 128–2048 | 11.27.25 |

## Valid configurations

Intersection of Vela support and FVP-stated support. **Not** a Cartesian product.

| # | platform | NPU | MAC configs | status |
| --- | --- | --- | --- | --- |
| C1 | SSE-300 | U55 | 32, 64, 128, 256 | **verified by capability probe** (512 rejected) |
| C2 | SSE-300 | U65 | 256, 512 | **verified by capability probe** (128 and 1024 rejected) |
| C3 | SSE-310 | U55 | 32, 64, 128, 256 | verified, both sides agree |
| C4 | SSE-310 | U65 | 256, 512 | verified |
| C5 | SSE-315 | U65 | 256, 512 | verified |
| C6 | SSE-320 | U85 | 128, 256, 512, 1024, 2048 | verified |
| **B1** | **MPS4 board** | **U85** | **1024 only** | verified from vendor config |

**19 simulated platform × MAC configurations, all now verified.** The six C1/C2
cells were resolved by capability probe on 2026-08-24: each candidate value was
offered to the FVP and accepted or rejected at init time.

### A nuance the probe exposed

`FVP_Corstone_SSE-300_Ethos-U55` **accepts `num_macs=100`.** The FVP range-checks
only the bounds; it does not validate the discrete set of legal MAC
configurations. So *"the FVP accepted it"* is not sufficient evidence that a
configuration is real.

The authoritative discrete set is Vela's `--accelerator-config` enumeration. A
configuration is valid only where **both** hold: Vela can target it, and the FVP
accepts it. The 19 cells satisfy both. Nothing in the sweep may use a MAC value
outside Vela's list merely because an FVP tolerates it.

### Two comparisons this inventory happens to enable

Worth stating because they are stronger than a generation sweep alone:

- **U55 @ same MAC across SSE-300 and SSE-310** — same NPU, different Corstone
  subsystem. Isolates the platform effect from the NPU effect.
- **U65 @ 256 across SSE-300, SSE-310 and SSE-315** — three Corstone generations,
  one NPU configuration.

Both are confounded by the Fast Models version skew (see MEASUREMENT_SEMANTICS)
and are qualitative until that is resolved.

## Workload set

From MLEK `resources_downloaded`, all INT8. NPU/CPU placement measured at
`ethos-u85-256`.

| model | domain | Vela `cycles_total` | CPU operators |
| --- | --- | --- | --- |
| `rnnoise_INT8` | noise reduction | 37,922 | 0 (0.0%) |
| `kws_micronet_m` | keyword spotting | 217,272 | 0 (0.0%) |
| `ad_medium_int8` | anomaly detection | 452,090 | 0 (0.0%) |
| `vww4_128_128_INT8` | visual wake words | 477,143 | 0 (0.0%) |
| `yolo-fastest_192_face_v4` | object detection | 1,297,666 | 0 (0.0%) |
| `mobilenet_v2_1.0_224_INT8` | image classification | 4,891,133 | 0 (0.0%) |
| `wav2letter_pruned_int8` | speech recognition | 17,720,421 | 0 (0.0%) |
| `dnn_s_quantized` | generic DNN | 24,452 | **2 (9.5%)** |

**Proposed: the seven fully-NPU models.** `dnn_s_quantized` is excluded from
scaling analysis because ~9.5% of its operators run on CPU, so its total does not
scale with MAC count and would flatten the scaling curve for reasons unrelated to
the NPU. It may be retained as a deliberate partial-fallback case if that is
wanted, but then it is reported separately and never pooled.

The seven span **467×** in estimated cycles, which is the dynamic range the
scaling and saturation questions need.

## Metrics

| class | metric | source |
| --- | --- | --- |
| estimate | `vela_estimated_cycles_total`, `_cycles_npu`, `_cycles_sram_access`, `_cycles_dram_access` | Vela CSV |
| estimate | `vela_estimated_inference_time` (= cycles ÷ assumed clock) | Vela CSV |
| memory | `sram_memory_used`, `dram_memory_used`, `*_total_bytes`, `total_npu_encoded_weights` | Vela CSV |
| structure | `passes_before_fusing`, `passes_after_fusing` | Vela CSV |
| simulated | NPU PMU cycle counters | FVP run |
| physical | `software_visible_completion_observation_cycles` | board |

Scaling metrics derived per model, per platform: raw speedup vs the smallest MAC
config, scaling efficiency (speedup ÷ MAC ratio), saturation point (first config
where efficiency falls below a threshold fixed **before** the sweep), and the
memory-bandwidth share of `cycles_total`.

## Procedure — frozen before the sweep

- **Warm-up:** exactly **one discarded inference** per configuration, carrying
  cold-cache and first-touch effects. Applied uniformly; the discarded run is
  recorded as discarded, never reported.
- **Measured runs:** **three deterministic FVP runs** per configuration. The FVP
  is deterministic, so repetition tests the harness rather than the device.
- **Agreement:** the three must be **exactly equal**. Disagreement is a **hard
  stop** for that configuration — never averaged, never median-filtered. A
  deterministic model that disagrees with itself means the harness is wrong, and
  averaging would hide exactly that.
- **Board:** 3 fresh boots × 10 consecutive runs, per-boot minima, no pooling
  before classification. Inherited from the qualified campaign design.
- **Invalid runs:** discarded with a named reason, never down-weighted, no
  top-up.

## Scaling definitions — frozen before results

Fixed now so that no threshold is chosen to fit a curve.

For model *m* on platform *p*, with MAC configurations `M₀ < M₁ < … < Mₙ` where
`M₀` is the smallest supported on that platform:

```
cumulative_efficiency(Mᵢ)
  = (cycles(M₀) / cycles(Mᵢ)) / (Mᵢ / M₀)

incremental_efficiency(Mᵢ₋₁ → Mᵢ)
  = (cycles(Mᵢ₋₁) / cycles(Mᵢ)) / (Mᵢ / Mᵢ₋₁)

saturation_point
  = the first Mᵢ where incremental_efficiency(Mᵢ₋₁ → Mᵢ) < 0.50
  = NONE_OBSERVED if no step falls below it
```

Both are reported. They answer different questions and the distinction matters:

- **cumulative** — how much of the ideal speedup has been realised *overall* by
  the time you reach `Mᵢ`. It decays smoothly and is dominated by early steps, so
  it can stay respectable well past the point where extra MACs have stopped
  paying.
- **incremental** — whether *this particular doubling* paid for itself. This is
  the one that identifies where scaling stops, which is why saturation is defined
  on it.

Using cumulative for saturation would systematically place the knee too late: a
strong first doubling props the cumulative figure up across later steps that
returned almost nothing.

**The 0.50 threshold is fixed now, before any result is seen.** It declares what
"saturated" will mean; it is not a description of a curve. If it proves
uninformative that is reported, not retuned. `NONE_OBSERVED` is a real outcome —
scaling had not saturated within the configurations the platform supports.

Baselines are **per platform**, since `M₀` differs (SSE-300/310 U55 start at 32,
SSE-320 at 128). Efficiency values are therefore comparable within a platform and
are **not** comparable across platforms as absolutes — consistent with the
cross-generation prohibition.

## Provenance required per run

Model digest, Vela version and full command line, `accelerator_config`,
`system_config`, `memory_mode`, FVP binary path and Fast Models version, every
`ethosu.*` parameter used (including the empty `extra_args`), harness commit, and
the output CSV digest.

## Board's role

```
Corstone-320 + Ethos-U85 @ 1024 MACs
```

**One** configuration, and only one — the FPGA is fixed. The board is the
physical-validation layer for the Corstone-320 simulation characterization. It is
**not** a source of cross-generation comparison, and it cannot validate any MAC
configuration other than 1024.

Concretely, board validation touches exactly one cell of the matrix: C6 @ 1024.

The 1024 figure is confirmed by two independent sources: the vendor header
(`CFG__NPU0_NUM_MACS 0x400`) and MLEK's own build logic, which states *"FPGA is
fixed at 1024 MACs"* and defaults that platform to config `Z1024`.

### The FVP and board binaries are not the same binary

MLEK's platform configuration carries this, verbatim:

> *"For sse-320 specifically, binaries built for FVP will not work on FPGA and
> vice versa."*

A separate `FPGA_PLATFORM_SSE_320` build option selects between them. So RQ3 does
not compare one artifact across two execution targets — it compares **two builds
of the same source**, each targeting its own memory map.

This is a stated limitation, not a defect: it means "same binary, different
platform" is unavailable as a control, and any FVP-versus-board deviation
includes whatever the two builds differ in. It reinforces the decision to treat
RQ3 as qualitative validation rather than numeric agreement, and both build
identities must be recorded in the provenance for every comparison.

## Research questions

**RQ1** — How do performance characteristics change across Corstone/Ethos-U
generations for representative workloads?

**RQ2** — How does performance scale with MAC configuration, and where does
scaling saturate because of workload, operator or memory characteristics?
Reported as: raw speedup, scaling efficiency, saturation point, workload/operator
sensitivity, memory-related bottlenecks.

**RQ3** — To what extent do the qualitative trends observed for
Corstone-320/U85 in FVP reproduce on the physical MPS4/FI101 platform?

### RQ3 validation criteria, preregistered

Numeric equality is **not** the criterion and is not expected.

| criterion | preregistered standard |
| --- | --- |
| ranking preservation | model ordering by cost identical between FVP and board |
| scaling-trend preservation | not testable on the board — only 1024 MACs exists |
| bottleneck consistency | models Vela marks memory-bound behave alike on both |
| repeatability | board floor reproduces across 3/3 boots |
| deviation | direction and magnitude reported as characterization, not agreement |

**Recorded now, before data:** the board offers one MAC configuration, so RQ3
cannot validate scaling behaviour — only per-model relative cost at 1024 MACs.
Any scaling claim remains simulation-only. Stating this after seeing results
would be choosing a standard to fit them.

## Estimated scale

| | |
| --- | --- |
| Vela compilations | 7 models × 19 configs = **133** |
| FVP runs | 133 × 3 repetitions = **399** |
| board runs | 7 models × 30 runs = **210** (needs separate authorization) |

Vela compile time is seconds per model. **FVP runtime remains UNMEASURED**, and
the attempt to measure it surfaced a blocker — see below.

## Blocker: the sweep needs MLEK builds, and MLEK is BLOCKED

An FVP run needs an application. The vehicle is MLEK's
`mlek_inference_runner.axf`, and it is built **per platform and per accelerator
configuration** — the memory map differs between Corstone generations.

72 prior build directories exist in the container (MLEK `26.03-8-gb2c0bb2`), but
a timing probe using `build-kws-256` on `FVP_Corstone_SSE-320` failed at image
load:

```
Warning: Failed to write bytes at address range [0x00008000..0x0006DC4B]
         when loading image "…/build-kws-256/bin/mlek_inference_runner.axf"
```

That build targets a different platform. Only two existing builds target SSE-320
(`build-prof-320-cpu`, `build-prof-320-cpu-scalar`) and both are CPU-only, with
no NPU configuration.

So the sweep requires **new MLEK builds — roughly one per (platform, accelerator
config), on the order of 19** — and MLEK is a standing BLOCKED constraint.

**This is the gating question for execution.** Runtime cannot be estimated
without at least one successful NPU-configured run, and that run cannot be
produced without a build. Three ways forward, for decision:

1. Lift the MLEK block for build purposes only, scoped to this sweep.
2. Authorize a single build + timing probe, enough to produce a runtime estimate
   without committing to the sweep.
3. Keep MLEK blocked and restrict the paper's simulation layer to **Vela
   estimates only**, dropping FVP-measured cycles. This is coherent — Vela
   estimates are uniformly defined across all 19 configs, which the PMU counters
   are not — but it removes the simulated-observation tier and weakens RQ3 to a
   Vela-versus-board comparison.

Until one is chosen, the FVP run count of 399 is **provisional** and its runtime
is **UNKNOWN**.
