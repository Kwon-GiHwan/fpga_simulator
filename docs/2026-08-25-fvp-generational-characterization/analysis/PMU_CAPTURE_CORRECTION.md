# Correction — the U85 memory counters were emitted, and my harness did not capture them

`DERIVED_RESULTS.md` reported:

> U85 `EXT*` / `SRAM*` family — **not evaluable** — the stock runner emits the
> AXI-named counters only; no EXT/SRAM series present in the UART profile.

**That is wrong.** The stock runner does emit them. The harness parser only ever
matched AXI names, so the fields were silently recorded as `None`.

## What the runner actually configures

`source/hal/source/components/npu/ethosu_profiler.c` selects the event set by
generation:

```c
#if defined(ETHOSU55) || defined(ETHOSU65)
    [0] NPU_ACTIVE
    [1] AXI0_RD_DATA_BEAT_RECEIVED
    [2] AXI0_WR_DATA_BEAT_WRITTEN
    [3] AXI1_RD_DATA_BEAT_RECEIVED
#elif defined(ETHOSU85)
    [0] NPU_ACTIVE
    [1] SRAM_RD_DATA_BEAT_RECEIVED
    [2] SRAM_WR_DATA_BEAT_WRITTEN
    [3] EXT_RD_DATA_BEAT_RECEIVED
    [4] EXT_WR_DATA_BEAT_WRITTEN      <- five, not four
#endif
```

And a real U85 UART profile block, from the executability evidence:

```
INFO - Profile for Inference:
INFO - NPU ACTIVE: 48560 cycles
INFO - NPU ETHOSU_PMU_SRAM_RD_DATA_BEAT_RECEIVED: 143 beats
INFO - NPU ETHOSU_PMU_SRAM_WR_DATA_BEAT_WRITTEN: 135 beats
INFO - NPU ETHOSU_PMU_EXT_RD_DATA_BEAT_RECEIVED: 7838 beats
INFO - NPU ETHOSU_PMU_EXT_WR_DATA_BEAT_WRITTEN: 36 beats
INFO - NPU IDLE: 526 cycles
INFO - NPU TOTAL: 49086 cycles
```

The data was on the wire the whole time.

## Field coverage actually achieved

```
ethos-u55   25 cells   total 25  active 25  idle 25  axi0rd 25  axi0wr 25  axi1rd 25
ethos-u65   14 cells   total 14  active 14  idle 14  axi0rd 14  axi0wr 14  axi1rd 14
ethos-u85   35 cells   total 35  active 35  idle 35  axi0rd  0  axi0wr  0  axi1rd  0
```

## Consequences, stated precisely

**1. The determinism verdict is unaffected in substance, but "19 fields" was
uniform only nominally.** For the 35 U85 cells, the three AXI fields compared
`None == None == None` — true, but carrying no information. `M1 == M2 == M3`
still held on every field that *was* captured: status, inference count, NPU
TOTAL, NPU ACTIVE, NPU IDLE, plus the four artifact and seven configuration
identities. The claim should be stated as such rather than as 19 informative
fields per cell.

**2. The U85 memory counters cannot be recovered from the frozen formal
evidence.** The Stage 1/2/3 records retain parsed fields only; `uart_tail` was
not kept in the formal records (it was kept in the executability evidence). So
the values exist for the *qualification* runs but not for the 222 formal samples.

**3. No analysis result changes.** The scaling, saturation, Vela-trend, and
ranking analyses all use `npu_total_cycles`, which was captured on 74/74 cells.
`pmu_within_generation.csv` is unaffected in its populated columns; only the
stated *reason* for the empty U85 columns was wrong.

## What is genuinely NOT_EVALUABLE

`CC_STALLED_ON_BLOCKDEP` — this one is confirmed. It exists in the core driver
enum (`dependencies/core-driver/include/pmu_ethosu.h:69,149`) but the stock
profiler never configures it for either generation, so it is never emitted. That
entry stands.

## What was not done

The frozen formal evidence was **not** modified and Stage 1/2/3 were **not**
re-run. Recovering the U85 memory counters into the formal dataset would require
re-acquisition under a corrected parser, which is a change to a frozen artifact
and therefore a decision to be taken, not an action to take unilaterally.

Reported rather than repaired.
