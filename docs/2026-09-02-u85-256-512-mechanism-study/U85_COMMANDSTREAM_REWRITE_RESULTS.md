# P0-C0 results — U85 command-stream rewrite feasibility

Date: 2026-09-02. Verdict:

```
C0-1 binary-format authority       SUFFICIENT (all load-bearing fields resolved)
C0-2 branch usage                  VERIFIED_NOT_PRESENT (0 branches in 18/18 streams)
C0-3 serializer identity           BYTE-IDENTICAL 18/18
C0-4 single-IRQ proof              PASS (all items)
C0-5 multi-IRQ proof (3 IRQs)      PASS (all items)
P0-C0                              QUALIFIED
P0-C full profiling qualification  NOT YET RUN (next stage; two carried questions below)
P0-D                               HOLD (unchanged)
```

Evidence root: `gihwan:/home/gihwan/mps4/U85_MECH_P0C0_20260902T003028Z`
(102 files, `EVIDENCE.sha256` manifest; includes every tool, build log, UART
capture, and instrumented artifact).

## C0-1 — authority table (all from source, none from byte patterns)

| field | authority | classification |
| --- | --- | --- |
| cmd word encoding: opcode[9:0], control[15:14], param/mask[31:16]; CMD1 = +1 payload word | `ethosu85_interface.h` struct bitfields (`npu_op_irq_t` L15189, `npu_op_branch_t` L23862) + disassembler key L14336 | VERIFIED_REWRITABLE |
| opcode tables | C enums `CMD0_OPCODE_*` / `CMD1_OPCODE_*`, mechanically extracted (172/… entries; fail-closed on unknown opcode or reserved control) | VERIFIED_REWRITABLE |
| container framing | `ethosu_driver.c`: FOURCC `COP1` (L54, checked L656), driver-action words; `COMMAND_STREAM` action carries 24-bit length **in words** (`(reserved<<16)\|length`, L700ff) | VERIFIED_REWRITABLE |
| TFLite carrier | custom op input tensor 0 = payload bytes (TFLM `ethos_u` kernel L57-58); tensor shape `[payload_bytes]`; **Buffer.data force_align 16** (schema; empirically 0 mod 16 in all vela outputs) | VERIFIED_REWRITABLE |
| branch target | `npu_op_branch_t.branch_target:32` "in bytes" — displacement semantics NOT further resolved | SEMANTICS_UNVERIFIED, **but VERIFIED_NOT_PRESENT in all 18 candidate streams** → not load-bearing for this campaign; any future stream containing a branch fails closed |
| termination | `NPU_OP_STOP` (cmd0=0); insertion never touches it | VERIFIED_REWRITABLE |
| integrity metadata | none found in payload path (no checksum/CRC fields in driver parse) | VERIFIED_NOT_PRESENT |
| IRQ runtime semantics | U85-only `STATUS.irq_history_mask[31:16]` / `CMD.clear_irq_history[31:16]` (L3548/L3714); stock driver never touches history | see C0-4 finding |

## C0-2 — branch/structure audit (18 artifacts = 6 workloads × 3 bindings)

Every stream: exactly one `COMMAND_STREAM` action, one partition, **0
branches**, 0 pre-existing IRQs, 1 STOP. Command counts 352–3231.
Side observation (structural, not analysis): `512@Low` and `512@Mid_512`
generate different command counts for every workload — the Vela
system-config alone changes the generated program, confirming the D2
decision's relevance.

## C0-3 — identity round trip

`parse → serialize(0 modifications) → bytes` byte-identical for 18/18
streams (`c0_audit_report.json`, `all_roundtrips_identical: true`).

## C0-4 / C0-5 — proofs on kws_micronet_m @ 512@Mid_512

Representative predeclared by structural simplicity (fewest commands, 352).
Insertion boundary predeclared: after the k-th `NPU_OP_CONV` launch.

| check | orig | control (copy, no IRQ) | irq1 | irq3 |
| --- | --- | --- | --- | --- |
| completes, count=1 | ✓ | ✓ | ✓ | ✓ |
| profiling layers | **0** | 0 | **1** | **3** |
| output CRC32 (12 B) | `0xCEE9B7FE` | same | same | same |
| NPU TOTAL after last reset | 114,070 | 114,070 | 106,040 | 51,040 |

- irq1 layer record `0: ccnt=8055 active=8007 …`; irq3 layer 0 record
  **identical byte-for-byte** — deterministic and stable op association.
- Sum coherence (descriptive): irq3 segments 8,055+42,025+13,025+51,040 =
  114,145 vs clean 114,070 → ≈25 cycles per IRQ boundary. Recorded, no
  threshold attached.
- AXF determinism: rebuilding `orig` from clean reproduced its SHA-256
  byte-identically.
- Stream hashes: orig cms `7e1a5a3b…`, irq1 cms `cd3164bf…`, irq3 cms
  `2e5a0a69…` (full values in the evidence manifest).

## Defects caught by the fail-closed design (and fixed before qualification)

1. **Flatbuffer alignment**: the first deep-copy writer ignored
   `force_align: 16`; buffers landed at 12/8/12 mod 16 and the driver's
   16-byte checks failed invoke — proven by direct offset measurement, fixed
   with a `Prep(16, len)` pre-alignment, and now guarded by a mandatory
   post-write alignment check on every output.
2. **Payload FOURCC**: initial parser missed the `COP1` header word; the
   unknown-action STOP caught it immediately.

## Device-side adaptation (carried to P0-C as an open question)

With the stock clear (`clear_irq` only) the first mid-stream attempt failed;
with `clear_irq_history=0xFFFF` added in `ethosu_dev_handle_interrupt`
(authority: the register pair above) the NPU demonstrably resumes. However
that first failure was **confounded** with the alignment defect, so:

- Q-A (P0-C item): rerun irq1 with the alignment-fixed stream but WITHOUT the
  history-clear, to isolate whether the history-clear is necessary — the
  answer defines the minimal qualified driver patch.
- Q-B (P0-C item): driver `LOG_SEVERITY=info` was needed to see the per-layer
  print; for measurement builds the print path must move off INFO (or the
  logging-contamination gates must account for it).

All temporary source changes (driver, device, app CRC print) were applied
per-build and reverted; each revert verified byte-identical against backups.
The MLEK/core-driver tracked tree is clean.
