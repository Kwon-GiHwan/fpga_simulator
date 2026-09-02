# The matrix splits in two — verified from the build system, not inferred

The 133 cells remain one **capability / executability universe**. Eligibility for
the three-repetition formal performance benchmark is a separate, narrower set.

```
capability / executability universe    19 configs × 7 workloads = 133 cells
primary performance benchmark (TA ON)  11 configs × 7 workloads =  77 cells
TA-OFF diagnostic / support             8 configs × 7 workloads =  56 cells
```

| universe | platform / NPU | configs | cells |
| --- | --- | --- | --- |
| **primary** | SSE-300 / U55 @ 32,64,128,256 | 4 | 28 |
| **primary** | SSE-300 / U65 @ 256,512 | 2 | 14 |
| **primary** | SSE-320 / U85 @ 128,256,512,1024,2048 | 5 | 35 |
| diagnostic | SSE-310 / U55 @ 32,64,128,256 | 4 | 28 |
| diagnostic | SSE-310 / U65 @ 256,512 | 2 | 14 |
| diagnostic | SSE-315 / U65 @ 256,512 | 2 | 14 |

## The split is observed, not assumed

The earlier note "TA is off for SSE-310/315" was a conclusion from a cycle-count
difference. It is now read directly out of the build system:

```cmake
# configuration_options/npu_opts.cmake
USER_OPTION(ETHOS_U_NPU_TIMING_ADAPTER_ENABLED "..." ON BOOL)

# platforms/mps3/build_configuration.cmake — and mps4, identically
if ((TARGET_SUBSYSTEM STREQUAL "sse-310") AND (DEFINED ...))
    set(ETHOS_U_NPU_TIMING_ADAPTER_ENABLED OFF CACHE BOOL "Use of TA" FORCE)
```

Default **ON**; forced **OFF** for `sse-310` and `sse-315` only. So SSE-300 and
SSE-320 are adapter-enabled and the other three configurations are not — which is
Arm's own recommended pairing for benchmarking.

Per-cell provenance records the **resolved** `CMakeCache` value rather than this
table, so each cell's adapter state is observed at its own build.

## The 56 are kept, and are not performance data

They remain in the support/executability matrix. They are not eligible for the
three-repetition formal benchmark, nor for any bandwidth- or latency-aware claim,
because with the adapter disabled the memory system is not modelled — cycle
counts there are a compute ceiling, not a system measurement.

The retracted claim stays retracted: "same NPU, different Corstone" is **not** a
platform-effect isolation, because the two sides differ in adapter state.

`SSE-300/U55@32` vs `SSE-310/U55@32` remains `CAUSE_RESOLVED` /
`NOT_A_PAPER_RESULT`. Nothing is to be "fixed" in SSE-310/315 — their behaviour
is correct for what they are. Only the scope of the claim changes.

## A comparison that also needs its scope narrowed

`SSE-300 / U55@256` vs `SSE-300 / U65@256` is the cleanest within-platform pair
available — same Corstone, same Fast Models family, same adapter state, same MAC
count. It is still **not** a pure NPU-microarchitecture effect: the memory mode
differs by NPU (`Shared_Sram` for U55, `Dedicated_Sram` for U65), which moves the
weights between SRAM and DRAM. It is reportable as a **system-level configuration
comparison**, not as a microarchitecture result.
