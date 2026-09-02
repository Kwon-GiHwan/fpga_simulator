# Stage 1 halted at the pre-flight gate — the AXF cannot reproduce by construction

```
FORMAL_FVP_SAMPLES            0
Stage 1 formal measurements   NONE STARTED
halt point                    artifact-reproduction gate, before cell 1
```

Stage 1 requires, per cell, before any FVP runs:

```
formal Vela SHA == qualification Vela SHA
formal AXF SHA  == qualification AXF SHA
```

The first cell fails the second condition. The instruction on this is explicit —
stop and report the cause, do not add a strip/normalize rule after seeing the
mismatch — so nothing was measured and no criterion was changed.

## What was observed

Rebuilt `rnnoise_INT8 / SSE-300 / ethos-u55-32` at the **identical workspace
path** used during qualification (`/tmp/xq/<cell_id>/build-a1`), same flags, same
arena:

| artifact | qualification | formal rebuild | verdict |
| --- | --- | --- | --- |
| vela | `7728c11b4b5b3302…` | `7728c11b4b5b3302…` | **reproduces** |
| AXF | `b2d500d3172e5c9e…` | `abe7d6668d0d2b61…` | **mismatch** |

Path sensitivity is not the cause — the path was held identical precisely because
Amendment 3 established that hazard for the V15 ELF.

## Root cause — localized to one line, three bytes

Two consecutive rebuilds *at the same path* also differ from **each other**:

```
build1  axf=ea1e210add3370fc…
build2  axf=b4dcca465d649ad7…

cmp -l  ->  3 differing bytes, total
```

```
source/app/main/Main.cc:38
    info("Version %s Build date: " __DATE__ " @ " __TIME__ "\n", PRJ_VER_STR);
```

The differing bytes are the clock time in that string literal:

```
build1:  Version %s Build date: Aug 24 2026 @ 18:36:56
build2:  Version %s Build date: Aug 24 2026 @ 18:37:49
```

The firmware embeds its own build timestamp. **Every** AXF is unique to the
second in which it was linked, so the qualification AXF hashes recorded during
the 133-cell pass cannot be reproduced by any later build. This is not corruption
and not specific to one cell — it makes the criterion unsatisfiable as written
for all 74 primary cells.

## The non-determinism is confined to the timestamp

Verified, diagnostically only — no formal measurement was run:

```
SOURCE_DATE_EPOCH=1756000000
  build1  axf=974e1fdf41c9731b0b766841a5d72536…
  build2  axf=974e1fdf41c9731b0b766841a5d72536…      identical
```

With the timestamp pinned the build is bit-reproducible. Timestamp aside, nothing
else in the toolchain varies between builds.

## Options — for decision, not adopted

No option is implemented. `FORMAL_FVP_SAMPLES = 0` and no measurement data
exists, so none of these is a threshold moved to fit a result.

**(a) Re-baseline the 74 with a pinned epoch — recommended.** Rebuild all 74
cells with `SOURCE_DATE_EPOCH` fixed, record the resulting AXF hashes as the
qualification reference, then enforce `formal == reference` literally. This
*satisfies* the criterion rather than relaxing it, and makes every later stage
byte-reproducible. Cost ≈ 74 rebuilds (~1.5 h). The vela hashes are already
proven reproducible 133/133 and are unaffected.

**(b) Canonical analysis ELF.** Compare a normalized ELF, as Amendment 3 did for
V15. This is the option the standing instruction warns against, since the
normalization would be introduced after observing a mismatch.

**(c) Narrow the reproduction requirement** to the artifacts that are
reproducible and semantically load-bearing — model, vela artifact, generated
model `.cc` — recording the AXF timestamp delta as documented and inert. This is
a relaxation and is not recommended.

## Why this is not a "non-executable" result

All 74 cells were `EXECUTABLE` at qualification. This is a build-reproducibility
property of the harness, not a property of any cell. Per the frozen tree it is a
`REPRODUCIBILITY / INFRASTRUCTURE` matter, and no cell's classification changes.
