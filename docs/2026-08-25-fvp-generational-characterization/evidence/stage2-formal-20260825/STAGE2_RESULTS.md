# Formal FVP Stage 2 — repetition #2, and the first real determinism test

```
anchor              paper-fvp-formal-presweep-anchor  5dae05d24d0e3fd8…  (FROZEN)
stage 1 evidence    paper-fvp-stage1-evidence-frozen  7989048c28638c91…  (FROZEN)
```

## Acquisition

```
Stage 2 attempted             74
Stage 2 successful         74/74

FORMAL_FVP_SAMPLES           148
cells at 2/3                  74
cells at 3/3                   0
```

## Artifact reproduction — re-gated on every run

The reference was **not** refreshed for repetition #2. Each cell was checked
against the same frozen anchor before its FVP started.

| gate | result |
| --- | --- |
| Vela SHA == anchor | **74/74** |
| generated `.cc` BODY SHA == anchor | **74/74** |
| raw AXF SHA == anchor (exact) | **74/74** |
| `timing_adapter` == ON | **74/74** |
| embedded literal == pinned epoch | **74/74** |

## Formal determinism

```
M1 == M2, full metric vector      74/74
mismatching cells                  0
```

The comparison covers all **19** equality-bearing fields fixed in
`DETERMINISTIC_METRIC_VECTOR.md` before any M2 existed — six PMU counters plus
inference count and status, four artifact identities, and seven configuration
identities. Not `NPU TOTAL` alone.

Verified twice: by the harness at acquisition time, and independently re-derived
afterwards from the frozen Stage 1 records. Both give 74/74.

The check is not a silent gate — it was mutation-tested before the stage ran:

| mutation | detected |
| --- | --- |
| `npu_total_cycles` off by 1 | ✅ |
| `axi0_rd_beats` off by 1 | ✅ |
| `axf_sha256` changed | ✅ |
| timing adapter flipped to OFF | ✅ |
| `wall_clock_s` / `owned_pgid` | correctly **not** equality fields |

## Harness

```
fatal 0   timeout 0   process death 0   wrong inference count 0
cleanup survivors 0   invalid records 0
```

## Runtime

```
FVP wall-clock   total 1327.4 s   median 4.51 s   max 128.02 s
stage elapsed    1.46 h
```

Scheduling evidence only.

## What is still absent

No scaling efficiency, saturation judgement, ranking, cross-generation trend, or
figures. With M1 and M2 both in hand the temptation is larger, and the only
computation performed was the exact `M1 == M2` integrity check.

Determinism is now evidenced across two repetitions. It **closes** at
`M1 == M2 == M3`.

## State

```
Stage 1 repetition #1     COMPLETE 74/74
Stage 2 repetition #2     COMPLETE 74/74, M1 == M2 74/74
Stage 3 repetition #3     HOLD
TA-OFF formal runs        NOT AUTHORIZED
Board paper measurements  HOLD
```
