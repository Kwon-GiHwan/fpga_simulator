# The arena retry rule, as executed — and why `N` is not the arena

The frozen rule:

> Attempt 1 platform-default arena. On the exact TFLM failure
> `Failed to resize buffer. Requested: N`, attempt 2 with the smallest
> build-system-supported arena `>= N`. One deterministic retry. No headroom.

The intent is unambiguous and is implemented as such. One detail in the literal
wording does not survive contact with the message format, so it is recorded here
rather than silently reinterpreted.

## `Requested: N` is one allocation, not the arena total

The full TFLM line carries three numbers:

```
TFLM - Failed to resize buffer. Requested: 12000192, available 2096904, missing: 9903288
```

with the identity **`available + missing == Requested`** (verified: 2096904 +
9903288 = 12000192). `N` is the size of the *single allocation that failed*,
measured against what remained in the arena — not the arena requirement.

The forced-RED case makes the consequence concrete. With a 256-byte arena:

```
Requested: 144, available 132, missing: 12
```

Here `N = 144` is **smaller than the arena that just failed**. "Smallest arena
`>= N`" is satisfied by the failing arena itself, so the literal rule prescribes
a retry identical to the attempt that failed — a guaranteed no-op, and a cell
that would land in `EXECUTABILITY_UNRESOLVED` for a reason that is an artifact of
the rule rather than of the platform.

## What is executed instead

```
retry_arena = ceil16(failing_arena + missing)
```

Every term comes from the failure message; nothing is chosen. This is the
smallest arena that satisfies the reported deficit, with no discretionary
headroom, still exactly one retry. On the recorded `wav2letter` / SSE-300 / U55
@32 case it yields **12,000,448 B (11.44 MiB)**, reproducing the "raise it to
12 MB" step already in the 2026-08-24 record.

When the deficit form is absent, the rule falls back to `ceil16(N)` and the
attempt records `form: REQUESTED_ONLY` so the two paths are never conflated.

## What this does not change

`missing` is the deficit of the **first** failing allocation. TFLM reports one
failure and stops, so a satisfied deficit can be followed by a new one. That case
is already covered by the frozen decision tree — *"retry produces another
unresolved allocation requirement → EXECUTABILITY_UNRESOLVED"* — and is recorded
that way. The retry is a single deterministic step, never a search.

Classification is unchanged:

```
retry link → SRAM region overflow   => NOT_EXECUTABLE_MEMORY
retry runs to completion            => EXECUTABLE
anything else                       => EXECUTABILITY_UNRESOLVED
```

Each attempt stores `requested`, `available`, `missing`, `failing_arena`,
`retry_arena` and the rule string, so the classification can be re-derived from
the evidence without re-running the cell.
