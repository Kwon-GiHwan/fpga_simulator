# Anchor supersession and formal-sample accounting

## Anchor lineage

| anchor | status |
| --- | --- |
| `eb3abec46147cc53…` | **SUPERSEDED BEFORE FORMAL DATA** — insufficient reconstruction parameters |
| `5dae05d24d0e3fd8…` | **authoritative** formal pre-sweep anchor |

The first anchor recorded artifact hashes but not the build parameters that
produce them, so a cell could not be rebuilt from the anchor alone. It failed on
the first Stage 1 cell. It was replaced while `FORMAL_FVP_SAMPLES = 0`, so no
measurement was ever taken against it.

**The anchor is now frozen.** If another missing field is discovered during
Stage 1, the correct action is to STOP and report — not to amend the anchor and
continue as was done here. That latitude existed only before any formal sample
was acquired.

## Formal-sample accounting

`FORMAL_FVP_SAMPLES` counts **acquired formal inferences**, not cells finished at
3/3:

```
Stage 1 attempted / successful    n / n
FORMAL_FVP_SAMPLES                n          (one M1 per completed cell)
cells at 1/3                      n
cells at 3/3                      0
```

If Stage 1 stops part-way, the M1 values already acquired are **not** discarded.
They remain acquired formal samples; a partial Stage 1 is simply not used for
scientific analysis.

## A claim that was too strong

Cell 1 produced `M1 = 112,059`, matching its qualification value exactly. That is
**sanity evidence** that the gate passed and the run was well-formed. It is not
confirmation of formal determinism.

Formal determinism closes only on

```
M1 == M2 == M3
```

across the three independent fresh processes. The qualification value is not one
of the formal repetitions and cannot stand in for one.
