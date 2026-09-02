# P0-C0 — U85 command-stream rewrite feasibility (amendment to the frozen plan)

Linked to: `U85_MECHANISM_ANALYSIS_PLAN.md`
(tag `paper-u85-mechanism-plan-anchor` = `a2a4689`). This amendment does not
modify the frozen plan; it inserts a feasibility stage before the P0-C
qualification, per the manager decision of 2026-09-02
(OPTION 1 = CONDITIONAL GO). Frozen BEFORE any experimental runtime
observation of an instrumented stream.

## Goal

Determine whether a compiled U85 command stream can be modified by inserting
`NPU_OP_IRQ` while preserving exact command-stream semantics apart from the
intended interrupt. **No formal mechanism data may be collected in this
stage.**

## Stages and gates (all fail-closed)

### C0-1 Binary-format authority

From vendor/source authority only (never inferred from byte patterns):
command encoding and widths, alignment, stream/container framing, length
fields, branch encoding and target semantics (absolute/relative/other),
relocation/offset tables, termination semantics, padding, integrity metadata,
and the TFLite/custom-payload metadata affected by stream-size changes.
Each rewrite-relevant field is recorded with authority source, file,
symbol/structure, semantics, and rewrite rule, classified
`VERIFIED_REWRITABLE` / `VERIFIED_NOT_PRESENT` / `SEMANTICS_UNVERIFIED`.
Any load-bearing `SEMANTICS_UNVERIFIED` → **STOP,
`REWRITE_PATH_NOT_QUALIFIED`.**

### C0-2 Branch usage audit

Using a decoder derived mechanically from the vendor header, inspect every P0
candidate stream (18 Vela artifacts of the frozen plan matrix; compile-only,
no runtime). Report per build: command count, branch opcode count, IRQ opcode
count, stream-size metadata, relocation-like structures. Nothing is inserted.
If IRQ insertion would displace branch targets, their correct rewrite must be
proven from authoritative semantics first — "probably still works" is
forbidden.

### C0-3 Parser/serializer identity

The rewrite framework is built READ-ONLY first. For every audited stream:
bytes → parse → serialize (zero modifications) → bytes must be
**byte-identical**. Any deviation → **STOP,
`SERIALIZER_NOT_IDENTITY_PRESERVING`.** No normalization of the binary.

### C0-4 Single-IRQ proof of concept

One representative workload/configuration chosen for structural simplicity
declared BEFORE any runtime measurement (not by favorable results). Exactly
one IRQ at one predeclared legal boundary. Validate: original runs; modified
runs; exactly one intended IRQ and no unexpected IRQ; normal completion;
output bit-identical; command ordering valid; branch targets (if any) resolve
to intended commands; no fatal state. Record original and modified stream
hashes.

### C0-5 Multi-IRQ structural proof

Only after C0-4: 2–3 IRQs at predeclared boundaries; validate IRQ
count/order, operation association, output identity, completion,
stream/branch integrity. No jump from one IRQ to every-operator insertion.

### C0-6 → resume P0-C

Only after C0-1..5 pass does the original P0-C qualification resume
(operator↔IRQ mapping, PMU snapshot/delta semantics, clean-vs-profiled
whole-model, output identity, ordering, per-layer reconstruction,
perturbation reported descriptively; no imported U55 threshold; no new
threshold after observation).

## PMU scope for the initial U85 profiler

Admitted: `CYCLE`, `NPU_ACTIVE`, `SRAM_RD`, `SRAM_WR`, `EXT_RD`, `EXT_WR`
(source-qualified). All stall-family events remain
`SEMANTICS_UNVERIFIED` / `NOT_EVALUABLE`; their absence does not block C0.
No U55/U65→U85 event equivalence may be invented.

## Fail-closed conditions (verbatim from the manager decision)

Undocumented branch/stream-length/relocation semantics; non-byte-identical
zero-modification round trip; output mismatch; unexpected or missing IRQ;
command/order ambiguity; incorrect branch destination; fatal NPU state;
unstable op_index↔operation identity; instrumentation semantics beyond the
intended IRQ. On STOP: classify `OPTION1_NOT_FEASIBLE_WITH_CURRENT_AUTHORITY`
and return to manager review before considering Option 2. **No silent
fallback to compiler-only analysis.**

## Success condition and holds

P0-D begins only if C0 = QUALIFIED **and** P0-C = QUALIFIED. Until then
P0-D/P0-E/P1–P4/narrative are all HOLD. Evidence freezes independently at
each stage boundary. STOP after P0-C0/P0-C for manager review before formal
acquisition.
