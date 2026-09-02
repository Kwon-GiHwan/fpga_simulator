# U85 mechanism study — limitations (declared, not minimised)

1. **Attribution granularity is bounded by IRQ-service merging.** NPU_OP_IRQ
   on the FVP behaves as raise-and-continue; consecutive small ops merge
   into one service window. One-hot history decoding recovers exact window
   membership, but cycles inside a mixed window are `NOT_SEPARATED` at op
   level. For rnnoise — the regressing workload — only 3/44 ops are
   individually separable; its decomposition floor is the 14-group common
   partition. This is a property of the observation mechanism at these op
   sizes, not a collection defect.

2. **Boundary residual.** Each ISR service loses/shifts a small constant
   (≈25–52 cycles depending on driver version; deterministic on the FVP).
   Group/whole-model sums agree within ±~1k accordingly. No threshold is
   attached; values are software-visible observations.

3. **dnn_s profiled arms NOT_AVAILABLE** — the CPU-op container carries
   `shape_signature`, outside the audited rewrite subset (fail-closed).
   Its whole-model REGRESS (+7,000, both bindings, artifact-identical) is
   from clean arms only; per-op decomposition was not collected.

4. **Q2 fields are schedule-level.** ublock/block/stripe attach via an
   order-based join from the verbose schedule; ops without an unambiguous
   join carry empty fields (`NOT_EVALUABLE`), never guesses. rnnoise's
   elementwise ops largely lack these fields.

5. **KERNEL_WAIT instrumentation.** The insertion tool also placed IRQs
   after `NPU_OP_KERNEL_WAIT` sync commands (proven harmless: outputs
   bit-identical; runs vector-exact). The analyzer maps them as SYNC
   pseudo-ops via offset-based queue matching. A future insertion revision
   should exclude sync commands at insertion time.

6. **Stall-family PMU events remain `SEMANTICS_UNVERIFIED`** and were not
   collected (plan scope). Memory-service behaviour is observed only through
   beat counters.

7. **Hardware-vs-compiler causality is `NOT_SEPARATED`** throughout, per the
   plan's wording contract. The one causal-adjacent computed fact is
   artifact identity: rnnoise/dnn_s regressions persist under both
   system-config bindings with byte-identical programs, so for them the
   system-config is excluded as the varying factor; MAC-count association
   remains unseparated from everything the MAC change implies.

8. **FVP scope.** All values are FVP cycle-model observations
   (`FVP_Corstone_SSE-320`, FM 11.27.25); nothing here is board data,
   latency, or `T_npu`.
