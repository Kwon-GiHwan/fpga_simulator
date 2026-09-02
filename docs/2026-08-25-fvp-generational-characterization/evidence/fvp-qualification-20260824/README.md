# FVP execution-pipeline qualification — 2026-08-24

One build, one run, under `MLEK_EXCEPTION`.

```
QUALIFICATION_RUNS = 1
FORMAL_FVP_SAMPLES = 0
```

**Neither the wall-clock nor the simulated cycles below are paper results.**
They exist to show the pipeline executes and to size the sweep.

## Preconditions, proven before the run

| | |
| --- | --- |
| target platform | SSE-320 (`TARGET_PLATFORM=mps4`, `TARGET_SUBSYSTEM=sse-320`, FPGA off) |
| accelerator config | Ethos-U85-1024 (`ETHOS_U_NPU_CONFIG_ID=Z1024`) |
| workload | `wav2letter_pruned_int8`, source `e0814a0e…b257` |
| CPU fallback | **0** — `CPU operators = 0 (0.0%)`, `NPU operators = 27 (100.0%)` |
| memory map | valid — image loaded with no write failures |
| NPU config confirmed | FVP `num_macs=1024`, TA `ta_config_u85_sys_dram_mid` |
| system config | `Ethos_U85_SYS_DRAM_Mid_1024`, `Dedicated_Sram` |
| network size | 3,491,110,876 MACs/batch |

## Results

| | |
| --- | --- |
| build | **SUCCESS**, 48 s |
| runner binary | `bf336fb42568efeb…acbe` |
| vela output | `4c5b640211f0aaa6…def7b` |
| image load | **PASS** |
| inference | **COMPLETED** — `Total number of inferences: 1`, `Inference completed.` |
| **wall-clock to completion** | **≈112 s** (FVP start 02:42:15 → last UART write 02:44:07.68) |
| FVP exit | did not self-exit; idled after the application terminated, and was killed |

### PMU counters reported by the run

```
NPU ACTIVE                             4,114,227 cycles
NPU IDLE                                     841 cycles
NPU TOTAL                              4,115,068 cycles
ETHOSU_PMU_SRAM_RD_DATA_BEAT_RECEIVED    463,085 beats
ETHOSU_PMU_SRAM_WR_DATA_BEAT_WRITTEN      40,950 beats
ETHOSU_PMU_EXT_RD_DATA_BEAT_RECEIVED   1,836,882 beats
ETHOSU_PMU_EXT_WR_DATA_BEAT_WRITTEN       19,045 beats
```

This **confirms the PMU audit empirically**: the `SRAM_*` and `EXT_*` events the
audit classified as U85-only are exactly the ones this U85 run emits. On U55/U65
these names do not exist, so this metric set is not portable across generations —
as predicted from the header, now observed in practice.

## Two operational facts

**The FVP does not exit when the application finishes.** The UART reached
`program terminating…` and `Inference completed.`, and the simulator kept
running. A sweep harness must detect completion from the **UART marker**, not
from process exit, or every run will hang until its timeout.

**A run dies with its SSH session.** The first attempt was launched over an SSH
command that closed; the UART showed initialization and stopped, which reads
exactly like a completed-but-quiet run. Relaunching detached (`setsid nohup`)
produced the full inference. The sweep harness must detach, and must distinguish
"finished" from "killed" by the completion marker rather than by output ending.

## Sweep projection

One measured point: **112 s** for `wav2letter` at **one** configuration
(SSE-320 / U85-1024).

```
naive reference projection   399 × 112 s ≈ 12.4 h
                             NOT an upper bound
                             NOT a validated full-sweep estimate
```

**Correction.** An earlier draft called this an upper bound. It is not, and the
reasoning that made it look like one was wrong. `wav2letter` is the heaviest
*workload*, but heaviest workload does not mean longest *simulation*:

- A **lower-MAC configuration** does the same work with fewer MACs per cycle, so
  it simulates **more** cycles. `u85-128` on the same model may run considerably
  longer than the 1024-MAC point measured here.
- A **different FVP binary or Fast Models version** simulates at its own speed.
  The installed set spans 11.22.35 to 11.31.28, and nothing measured here says
  they are comparably fast.

So 112 s is one sample from one cell, not a maximum over the matrix. It is a
reference point for scaling arithmetic and nothing more.

A defensible planning range needs:

1. **Vela cycle estimates for all 133 model × config pairs** — compilation only,
   no FVP. Gives the simulated-cycle distribution the runtime depends on.
2. **A second wall-clock point on the same FVP and configuration** — a short
   workload (`rnnoise_INT8`) at SSE-320 / U85-1024, to separate fixed per-run
   overhead from per-cycle cost **locally**.

The resulting `T = fixed + k·cycles` fit is **local to SSE-320 / U85-1024** and
must not be generalized across other FVP binaries, Fast Models versions, or MAC
configurations.

## Formal harness requirements — frozen

Derived from the two failures this probe exposed. These are requirements, not
recommendations.

```
SUCCESS  =  UART "Inference completed."
         +  expected inference count
         +  no fatal / NPU error

SUCCESS  ≠  FVP process exit
```

- **The FVP must be detached from the SSH session.** A run dies with its session,
  and its truncated UART is indistinguishable from a quiet success.
- **Record the owned PID / process group** at launch.
- **Wait on the UART completion marker**, never on process exit — the FVP does
  not exit when the application finishes.
- **Output silence is not success.** A run whose output merely stopped is a
  failure until the marker says otherwise.
- **Process death before the marker is a failure**, recorded as one.
- **Explicit process-group termination after completion**, followed by a
  **cleanup check**.
