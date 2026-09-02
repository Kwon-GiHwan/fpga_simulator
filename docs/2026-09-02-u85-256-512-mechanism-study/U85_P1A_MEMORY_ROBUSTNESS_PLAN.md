# P1-A — memory-configuration robustness of the U85 256→512 direction

Frozen BEFORE any P1 acquisition. Manager authorization: P0 ACCEPTED, P1
authorized, narrative HOLD. All P0 frozen evidence is preserved exactly;
P1 evidence is a new namespace.

**This is a memory-CONFIGURATION experiment, not a bandwidth experiment**:
a memory-mode change may jointly move weight placement, arena headroom,
DMA behaviour, Vela tiling/scheduling and the command stream. Artifact
identity is recorded precisely so runtime configuration sensitivity is
never conflated with compiler-generated program changes.

## Capability audit of the prior-study tuples (source authority)

Authority: pinned `scripts/vela/default_vela.ini` (U85 sections), MLEK
`npu_opts.cmake`.

| prior-study tuple | verdict |
| --- | --- |
| Sram_Only × DRAM_High | component `DRAM_High` NOT_PRESENT for U85 (only `SYS_DRAM_{Low,Mid_512,Mid_1024,High_2048}`); memory mode SUPPORTED → **admitted as amended tuple T-SO** (below) |
| Sram_Only × Flash_High | **NOT_SUPPORTED** — no U85 Flash system config exists; all four U85 configs set `axi1_port=Dram`. Excluded, recorded |
| Shared_Sram × DRAM_High | same amendment → **admitted as T-SH** |
| Dedicated_Sram × DRAM_High | same amendment → **T-DS = the P0 baseline**; frozen P0 clean cells are REUSED, not re-acquired |

Registered supersession: the tuple's system-config component is bound to the
P0 B-frozen convention (`SYS_DRAM_Low`@256, `SYS_DRAM_Mid_512`@512), so P1-A
varies exactly one axis — `--memory-mode` / `ETHOS_U_NPU_MEMORY_MODE` ∈
{Sram_Only, Shared_Sram, Dedicated_Sram} — against the P0 baseline.
Additional declared context: MLEK's timing-adapter config is itself
MAC-dependent (Z256→`ta_config_u85_sys_dram_low`, Z512→`..._mid`); this was
equally true of the P0 baseline and is part of what "the 256→512 boundary"
means on this stack.

Memory-mode semantics from the ini (recorded): Sram_Only
(const/arena/cache=Axi0), Shared_Sram (const=Axi1, arena/cache=Axi0),
Dedicated_Sram (const/arena=Axi1, cache=Axi0, cache 384 KiB).

## Matrix

```
4 workloads  rnnoise_INT8, dnn_s_quantized, vww4_128_128_INT8,
             yolo-fastest_192_face_v4          (exact P0 model SHAs)
× 2 MAC      256, 512  (P0-convention system-config per MAC)
× 3 modes    T-SO, T-SH, T-DS
= 24 cells   (8 T-DS cells reused from frozen P0 clean arms; 16 new)
```

Clean whole-model arms ONLY (no per-layer profiling; P1-B is separate and
unauthorized). Build contract unchanged (SOURCE_DATE_EPOCH, arena constant,
TA ON, app CRC print as in P0). 3 fresh FVP runs per new cell, full-vector
exact equality. A link or runtime allocation failure is recorded
`NOT_EXECUTABLE_MEMORY` — a result, not a gap; no arena retuning.

## Preregistered analysis

- Direction per (workload, mode): sign of `clean_512 − clean_256`
  (P0 rule verbatim; no thresholds).
- Artifact identity per (workload, MAC): compare Vela artifact SHA-256
  across modes → `SAME_ARTIFACT_ACROSS_BINDINGS` or `DIFFERENT_ARTIFACT`
  per mode pair; likewise the 512-artifact identity across MACs is already
  fixed (always DIFFERENT by accelerator-config).
- Reported: supported tuples; executable cells; per-(workload, mode)
  direction; configurations reproducing/removing each reversal; artifact
  identity table; rule failures.
- **No aggregate robustness score is computed.** No causal vocabulary
  beyond ASSOCIATED_WITH / CONSISTENT_WITH / NOT_SEPARATED /
  NOT_EVALUABLE.

## Stop

After the clean robustness matrix is frozen: STOP and report. P1-B
(selective per-layer profiling) does not start without manager review.
