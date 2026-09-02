# Compiled-source closure — what actually entered the build

`git status` proves the tracked files are unmodified. It does **not** prove that
no untracked file entered the build through a glob. This closure is taken from
the build system's own record of what it compiles.

Extracted with `CMAKE_EXPORT_COMPILE_COMMANDS=ON` for both platform families —
`mps3/sse-300` (U55/U65 cells) and `mps4/sse-320` (U85 cells).

```
MLEK commit             b2c0bb2884698b7328f65c41b7c8c51ca9bec386
tracked modifications   0
compiled sources        409 distinct files, each with sha256
untracked in own repo   0
outside the kit tree    2  (the generated model .cc, one per platform probe)
```

The two out-of-tree entries are the vela artifact emitted as a C byte array —
that *is* the per-cell model, and it is hashed per cell as `generated_cc_sha256`.

## Dependency pins

Every dependency is a clean checkout at a pinned commit:

| repo | commit | modified |
| --- | --- | --- |
| `avh` | `11012b5` | 0 |
| `cmsis-6` | `fdbbc52f` | 0 |
| `cmsis-dsp` | `e366b076` | 0 |
| `cmsis-nn` | `a3f311a` | 0 |
| `core-driver` | `0356707` | 0 |
| `core-platform` | `02d0290` | 0 |
| `cortex-dfp` | `cd38dbb` | 0 |
| `executorch` | `17adba19d0` | 0 |
| `tensorflow` | `f2b2b3f5` | 0 |

## A false positive worth recording

Checking membership with `git ls-files` in the **kit** repo alone reported 16
TFLM sources as untracked. They are not — they live in the `tensorflow`
submodule, which the parent repo cannot enumerate. Membership must be tested
against each source's own repository. Corrected, the count is 0.

Recording that mistake matters: the uncorrected form would have manufactured a
provenance alarm on every future run.

## An independent guard the build system already provides

MLEK validates the vela artifact's NPU against the requested configuration:

```
ValueError: NPU config mismatch for .../rnnoise_INT8_vela.tflite:
            requested U85 but model is U55.
```

Found by feeding a U55 artifact to a U85 configure.

**Defence in depth only — not a provenance authority.** What this check
demonstrably catches is an *accelerator-generation* mismatch. Whether it equally
prevents linking the wrong **workload** within the same generation is a separate
question and has not been established here, so it must not be promoted to "a
wrong artifact can never enter a cell".

The load-bearing provenance remains the hash chain, unchanged:

```
model sha256 -> vela artifact sha256 -> generated model .cc sha256
             -> AXF sha256 -> cell identity
```

## Scope of this closure

Two representative builds were taken: `mps3/sse-300` and `mps4/sse-320`. That is
**not** sufficient to generalize to all 133 cells. The matrix contains four
target subsystems with distinct build graphs, and `sse-310`/`sse-315` are already
known to take a *target-dependent branch* — the timing adapter is forced off for
exactly those two. A build graph that branches on target cannot be assumed
identical across targets.

```
SSE-300   closure captured
SSE-320   closure captured
SSE-310   REQUIRED before the formal pass
SSE-315   REQUIRED before the formal pass
```

Completion requirement, not a blocker for the executability pass. Deferred until
the pass finishes rather than run alongside it, because concurrent extraction is
what corrupted the disk telemetry of cells 8-12.
