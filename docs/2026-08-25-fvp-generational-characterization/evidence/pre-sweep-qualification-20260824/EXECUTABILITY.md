# The compile matrix is not the execution matrix

**133 cells compile. Fewer than 133 can run.** This was found by probe, not
assumed, and it changes the sweep plan.

## What happened

`wav2letter_pruned_int8` on SSE-300 / U55 @ 32, built and launched normally:

```
TFLM - Failed to resize buffer. Requested: 12000192, available 2096904,
                                missing: 9903288
ERROR - tensor allocation failed!
ERROR - Failed to initialise model
INFO - program terminating...
```

The default activation buffer is `0x00200000` (2 MB); the model needs ~11.4 MB.
Raising it to 12 MB does not help — it fails at **link**:

```
ld: section `.sram' will not fit in region `SRAM'
ld: region `SRAM' overflowed by 10485760 bytes
```

SSE-300's SRAM cannot hold the arena this model requires under `Shared_Sram`.
**The cell is not executable.** Not a tuning problem; a platform memory limit.

## Why this is structural, not incidental

Arena demand depends on the **memory mode**, which is per-NPU:

| NPU | memory mode | weights | consequence |
| --- | --- | --- | --- |
| U55 | `Shared_Sram` | in SRAM | large models exhaust SRAM |
| U65 / U85 | `Dedicated_Sram` | in DRAM | arena stays small |

The same `wav2letter` ran on SSE-320 / U85-1024 with an arena of just
**334,356 bytes**, because the weights sat in DRAM. On U55 they do not.

Vela compiling a cell says nothing about whether it runs. Vela is a compiler; it
does not link against a platform memory map.

## Consequence for the sweep

The 133 builds are not merely a build step — **they are the executability
filter**, and some will fail. The determination procedure:

1. Build with the default arena.
2. Run. If the UART reports `Failed to resize buffer. Requested: N`, rebuild with
   an arena ≥ N.
3. If that build fails to link with an SRAM overflow, the cell is
   **NOT_EXECUTABLE** and is recorded as such — never silently dropped.

`NOT_EXECUTABLE` is a real result. It says a workload does not fit a
configuration, which is itself a finding about the platform rather than a gap in
the data.

**The formal sample count cannot be fixed until this filter has run.** 399 assumed
every cell runnable, and at least one does not.

## A harness requirement this exposed

My probe waited for the completion marker and would have waited to its 3-hour
timeout: the application printed `ERROR - Failed to initialise model` and
`program terminating...`, the FVP kept running at ~100% CPU, and no marker ever
came.

The manager's rule already anticipated this — success is *"marker + expected
inference count + no fatal/NPU error"* — but my implementation only watched for
the marker. Fatal-error detection is now required:

```
FAILURE  ←  "ERROR - Failed to initialise model"
FAILURE  ←  "tensor allocation failed"
FAILURE  ←  "program terminating..." seen without the completion marker
```

Without it, every non-executable cell burns its full timeout while pinning a core.
