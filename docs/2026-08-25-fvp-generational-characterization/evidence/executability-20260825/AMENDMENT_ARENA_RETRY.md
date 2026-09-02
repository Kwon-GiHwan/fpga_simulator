# Amendment — arena retry derives from the reported deficit

**Formal samples observed before this correction: 0.**

This is not a relaxed threshold. The old rule mis-modelled the *field semantics*
of a TFLM diagnostic; a real negative exposed it, and the contract is corrected
to match the message.

## Old rule (withdrawn)

```
retry_arena = smallest supported arena >= Requested
```

It read `Requested` as the total arena requirement.

## Finding

The TFLM line carries three numbers and an identity:

```
Failed to resize buffer. Requested: R, available: A, missing: M
              A + M == R
```

`R` is the size of the **single allocation that failed** against what remained in
the arena — not the arena requirement. `R` can therefore be *smaller* than the
arena that just failed, which the forced-RED case demonstrates:

| case | failing_arena | R | A | M |
| --- | --- | --- | --- | --- |
| forced RED (256 B arena) | 256 | **144** | 132 | 12 |
| recorded `wav2letter` / SSE-300 / U55@32 | 2,097,152 | 12,000,192 | 2,096,904 | 9,903,288 |

In the first row the old rule is satisfied by the failing arena itself, so it
prescribes a retry byte-identical to the attempt that just failed.

## Correction

```
minimum_retry_arena = failing_arena + M
retry_arena         = align_up(minimum_retry_arena, ARENA_ALIGNMENT)
```

| case | sum | retry_arena |
| --- | --- | --- |
| forced RED | 268 | **272** |
| `wav2letter` | 12,000,440 | **12,000,448** (11.44 MiB) |

Every term comes from the failure message. Nothing is chosen, no headroom, and
still exactly one retry.

## ARENA_ALIGNMENT = 16 — proven, not fitted

Pinned from source before being used, and independent of the arithmetic above.
The value in force for these builds is the **NPU path**; the non-NPU default is a
different `#define` that happens to agree.

| authority | location | value | in force here |
| --- | --- | --- | --- |
| Ethos-U memory config | `source/hal/source/components/npu/include/ethosu_mem_config.h:25` — `#define ETHOS_U_MEM_BYTE_ALIGNMENT 16` | 16 | **yes** — all 133 cells build with `ARM_NPU` |
| MLEK buffer attributes | `source/app/main/include/BufAttributes.hpp:29,34` — `BYTE_ALIGNMENT = ETHOS_U_MEM_BYTE_ALIGNMENT`, else `16` | 16 | via the above |
| TFLM arena constant | `dependencies/tensorflow/.../micro_arena_constants.h:24` — `constexpr int MicroArenaBufferAlignment() { return 16; }` | 16 | allocator-internal |

`activationBuf` is declared `__attribute__((aligned(BYTE_ALIGNMENT)))`, so the
alignment applies to the buffer this rule resizes. Empirically consistent in
independently built binaries:

```
31000000 00200000 b _ZN3arm3appL13activationBufE     addr%16 == 0, size%16 == 0
```

```
ARENA_ALIGNMENT = 16
```

## Frozen classification tree

```
Attempt 0: platform-default arena (0x00200000)
  success                                   => EXECUTABLE
  exact failure, require A + M == R
    derive retry = align_up(failing_arena + M, 16)

Attempt 1: exactly one deterministic retry
  success                                   => EXECUTABLE
  link fails, SRAM region overflow          => NOT_EXECUTABLE_MEMORY
  another allocation shortage               => EXECUTABILITY_UNRESOLVED
  unrelated build/runtime failure           => EXECUTABILITY_UNRESOLVED
```

A second `missing` is **never** consumed. Taking it would turn a preregistered
one-step policy into a search.

`NOT_EXECUTABLE_MEMORY` carries real strength under this tree: if the *minimum*
increment needed to clear the first failure cannot be linked, no larger arena fits
that SRAM map either. That is a memory-capacity limitation, not a tuning gap.
