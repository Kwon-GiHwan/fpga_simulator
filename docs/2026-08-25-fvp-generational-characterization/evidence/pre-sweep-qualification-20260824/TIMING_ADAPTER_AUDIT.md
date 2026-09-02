# SSE-300 vs SSE-310 static audit — cause found, and it reshapes the matrix

The ~4× cycle discrepancy is **RESOLVED**, not unresolved. It is a documented
platform difference, and it disqualifies two platforms from bandwidth/latency
benchmarking.

## The audit

Same workload, same NPU, same MAC count, side by side:

| | SSE-300 / U55@32 | SSE-310 / U55@32 |
| --- | --- | --- |
| model hash | identical | identical |
| **vela artifact** | `7728c11b…` | **`7728c11b…` — byte-identical** |
| NPU identity | U55 | U55 |
| `num_macs` | 32 | 32 |
| memory mode | `Shared_Sram` | `Shared_Sram` |
| Vela system config | `Ethos_U55_High_End_Embedded` | `Ethos_U55_High_End_Embedded` |
| `--fast` | not used | not used |
| **timing adapter** | **ON** | **OFF** |
| observed NPU TOTAL | 112,059 | 27,059 |

The Vela artifacts are **byte-identical**, so the NPU command stream is the same
program. The difference is entirely platform-side, and the audit isolates it to
one variable: the timing adapter.

## Cause

MLEK disables the timing adapter for Corstone-310 deliberately. Its build
configuration says so:

> *"Arm Corstone-310's timing adapter behaviour is very different to Arm
> Corstone-300 and cannot be used for bandwidth/latency related performance
> sweeps for the Arm Ethos-U NPU."*

And its documentation is explicit:

> *"All Arm Corstone-300 based platform implementations fully support the use of
> `timing adapter` … However, the timing adapter implementations in Arm
> Corstone-310 and Arm Corstone-315 are different and unsuitable for such
> benchmarking. … the CMake configuration is set up to ignore the timing
> adapters … entirely for Arm Corstone-310 and Arm Corstone-315. If you want to
> do any NPU performance benchmarking for different bandwidth and latency
> conditions, **we recommend using the Arm Corstone-300 and Arm Corstone-320
> implementations.**"*

With the timing adapter off, memory latency and bandwidth constraints are not
modelled, so the NPU stalls less and reports far fewer cycles. 112,059 → 27,059
is that effect, not a faster platform.

## Measured timing-adapter state, all builds

| build | subsystem | NPU | TA |
| --- | --- | --- | --- |
| qual-320-u85-1024 | sse-320 | U85 | **ON** |
| probe-p300u55_32 | sse-300 | U55 | **ON** |
| probe-p300u65_256 | sse-300 | U65 | **ON** |
| probe-p310u55_32 | sse-310 | U55 | OFF |
| probe-p310u65_256 | sse-310 | U65 | OFF |
| probe-p315u65_256 | sse-315 | U65 | OFF |

## Consequence for the matrix

**Benchmarking-valid platforms are SSE-300 and SSE-320 only.**

| platform | configs | benchmarking-valid |
| --- | --- | --- |
| SSE-300 / U55 | 32, 64, 128, 256 | **yes** |
| SSE-300 / U65 | 256, 512 | **yes** |
| SSE-320 / U85 | 128, 256, 512, 1024, 2048 | **yes** |
| SSE-310 / U55 | 32, 64, 128, 256 | no — TA off |
| SSE-310 / U65 | 256, 512 | no — TA off |
| SSE-315 / U65 | 256, 512 | no — TA off |

**11 of 19** configurations are valid for bandwidth/latency performance claims.

### A claim of mine that this retracts

I previously offered two "clean isolations" as a strength of the inventory:
same-NPU-across-Corstone-generations for U55 (SSE-300 vs SSE-310) and U65@256
across SSE-300/310/315.

**Both are invalid.** They differ in timing-adapter state, so they are not
controlled comparisons — they compare a memory-constrained model against an
unconstrained one. Cycle differences across those pairs are dominated by whether
memory was modelled at all.

What survives is cleaner than what it replaces: cross-generation comparison runs
**SSE-300 (U55, U65) against SSE-320 (U85)**, both timing-adapter enabled, which
is exactly the pairing Arm recommends.

## Classification

```
OBSERVED_IN_QUALIFICATION
CAUSE_RESOLVED — timing adapter enabled on SSE-300, disabled on SSE-310/315 by design
NOT_A_PAPER_RESULT
```

Not `CAUSE_UNRESOLVED`: the audit found the variable, it is documented upstream,
and it is deliberate rather than a misconfiguration on our side. Nothing to fix —
the SSE-310/315 behaviour is correct for those platforms. What changes is the
**scope of claims** they can support.
