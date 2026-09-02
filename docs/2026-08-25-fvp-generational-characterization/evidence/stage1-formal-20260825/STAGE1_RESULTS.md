# Formal FVP Stage 1 — repetition #1 across the 74 primary cells

```
anchor            paper-fvp-formal-presweep-anchor
ANCHOR_DIGEST     5dae05d24d0e3fd87a7a4b964693c52b284055a47a7061046f40ea1efd40d8ef  (FROZEN)
```

## Acquisition

```
Stage 1 attempted             74
Stage 1 successful         74/74

FORMAL_FVP_SAMPLES            74
cells at 1/3                  74
cells at 3/3                   0
```

## Artifact reproduction — gated before every run

Each cell had to reproduce its anchored artifacts *before* its FVP was allowed to
start. No cell ran on an unverified binary.

| gate | result |
| --- | --- |
| Vela SHA == anchor | **74/74** |
| generated `.cc` BODY SHA == anchor | **74/74** |
| raw AXF SHA == anchor (exact) | **74/74** |
| `timing_adapter` == ON | **74/74** |
| embedded literal == pinned epoch | **74/74** |

`74/74` distinct AXFs in the stage — no two cells ran the same binary.

## Harness

```
fatal                     0
timeout                   0
process death             0
wrong inference count     0
cleanup survivors         0
invalid formal records    0
```

A global scan after the stage shows **0 live FVP processes**. Six PIDs are
present and all are `Z` defunct — the same six that predate this work, unchanged.

## Runtime

```
FVP wall-clock   total 1329.1 s   median 4.41 s   max 127.77 s
                 max cell: wav2letter / SSE-320 / ethos-u85-128
stage elapsed    1.46 h  (rebuild + gate + run per cell)
```

Wall-clock is **scheduling evidence only**, not a performance metric.

## What is deliberately absent

No scaling efficiency, no saturation judgement, no workload ranking, no
generational interpretation, and no figure or table of final results. The 74 M1
values are one repetition of three; the matrix is not analysed at this stage.

Formal determinism is **not** claimed. It closes only on `M1 == M2 == M3` across
three independent fresh processes. That several M1 values coincide with their
qualification counterparts is sanity evidence that the gate and run were
well-formed — the qualification value is not one of the three repetitions.

## State

```
Stage 1 repetition #1        COMPLETE 74/74
Stage 2 repetition #2        HOLD
Stage 3 repetition #3        HOLD
TA-OFF formal runs           NOT AUTHORIZED
Board paper measurements     HOLD
```
