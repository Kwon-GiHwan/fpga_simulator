# Formal FVP Stage 3 — repetition #3, determinism closed

```
anchor              paper-fvp-formal-presweep-anchor  5dae05d24d0e3fd8…  (FROZEN)
stage 1 evidence    paper-fvp-stage1-evidence-frozen  7989048c28638c91…  (FROZEN)
stage 2 evidence    paper-fvp-stage2-evidence-frozen  98987f52b39f86bb…  (FROZEN)
```

## Acquisition

```
Stage 3 attempted             74
Stage 3 successful         74/74

FORMAL_FVP_SAMPLES           222
cells at 3/3                  74
```

## Artifact reproduction

| gate | result |
| --- | --- |
| Vela SHA == anchor | **74/74** |
| generated `.cc` BODY SHA == anchor | **74/74** |
| raw AXF SHA == anchor (exact) | **74/74** |
| `timing_adapter` == ON | **74/74** |
| embedded literal == pinned epoch | **74/74** |

The reference was never refreshed across the three repetitions.

## Formal determinism — closed

```
M1 == M2 == M3, full metric vector      74/74
mismatching cells                        0
```

All 19 equality-bearing fields, fixed before Stage 2 produced a result and
unchanged since: six PMU counters, inference count and status, four artifact
identities, seven configuration identities.

Verified twice — by the harness against **both** priors at acquisition time, and
re-derived independently afterwards from the two frozen evidence sets. Both give
74/74.

Mutation-tested before the stage ran: an `M3` differing by a single cycle is
detected against `M1` **and** against `M2`.

No 2/3 majority, no `M3` retry, no median or average, and no tie-break from the
qualification value was used or is available in the code path — a mismatch
returns `DETERMINISM_FAILURE` and stops the stage.

## Harness

```
fatal 0   timeout 0   process death 0   wrong inference count 0
cleanup survivors 0   invalid records 0
```

## Runtime

```
FVP wall-clock   total 1327.5 s   median 4.41 s   max 127.61 s
stage elapsed    1.46 h
```

Scheduling evidence only.

## Acquisition and analysis stay separated

Acquisition is complete and the evidence is frozen. **No analysis has been
performed** — no scaling efficiency, saturation judgement, ranking,
cross-generation trend, or figures. The only computation across the three stages
was the exact determinism check.

## State

```
Stage 1 / 2 / 3           COMPLETE 74/74 each
FORMAL_FVP_SAMPLES        222
cells at 3/3              74
M1 == M2 == M3            74/74

Analysis                  NOT STARTED — awaiting authorization
TA-OFF formal runs        NOT AUTHORIZED
Board paper measurements  HOLD
```
