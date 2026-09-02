# Discussion points

Drawn only from `paper-fvp-analysis-results-frozen`. No new computation.

## The compiler predicts shape better than steps

Vela matched the FVP saturation classification in 19 of 20 ladders and preserved
normalised speedup ordering in 19 of 20, yet per-step incremental class agreement
ranged from `4/4` down to `0/1`. The practical reading: a compiler estimate is a
reasonable instrument for deciding *whether* a configuration will keep scaling,
and a poor one for deciding *how much* a specific MAC step will buy.

This matters for design-space exploration, where Vela is often used to prune
configurations before any simulation. Pruning on trend is supported by this data;
ranking candidate configurations on estimated magnitude is not.

## Ordering is the portable quantity

Workload ranking was stable across configurations (`rho` median 1.0000, minimum
0.9429 over 55 pairs) while absolute cycles are not comparable across generations
at all. The portable result of this study is ordinal.

That also shapes what board validation should test. With a single board MAC
configuration, ranking preservation is still comparable even though MAC scaling
and absolute cycles are not — so the board set can be small and still decisive.

## Compilation is not deployment

All 133 cells compiled under Vela; 6 could not run. Every failure reached a
linker SRAM overflow after the deterministic minimum-increment retry, meaning the
smallest arena that could clear the first allocation failure already did not fit.

The useful general statement is that compiler acceptance does not establish
deployability against a concrete platform memory map. For the largest workload,
executability — not throughput — was the binding constraint.

This also affects how a scaling table should be read: a missing cell is a
**result**, not a gap in the data collection.

## Saturation was rare within the tested range

One ladder of 21 crossed the preregistered threshold. The honest framing is that
the explored MAC range mostly sat below saturation for these workloads, not that
these workloads scale indefinitely. The distinction is the difference between a
measurement and an extrapolation.

## Methodology points worth surfacing in the paper

Several findings are about *how to measure*, and are reusable beyond this study:

- **A simulator's timing adapter can silently change what is being measured.**
  Two platforms running a byte-identical NPU command stream differed ~4× purely
  by adapter state. Reporting that as a platform comparison would have been
  wrong, and nothing in the cycle counts themselves signalled it.
- **Firmware that embeds its own build timestamp is not byte-reproducible.**
  Three bytes of `__TIME__` made every binary unique, which defeats artifact
  reproduction until the build epoch is pinned to something derived from source
  identity.
- **A generated intermediate can carry non-determinism that never reaches the
  binary.** The model `.cc` differed between builds while the linked AXF was
  byte-identical — which is why the executable, not the intermediate, is the
  right identity to enforce exactly.
- **Executability classification belongs before the sweep, not inside it.** The
  formal sample count could not be fixed until the executability filter had run;
  399 assumed every cell runnable and the true figure was 222.

## What this dataset cannot settle

Cross-generation absolute performance, any architectural cause for the observed
scaling distribution, and whether the `wav2letter`/U55 limit is attributable to
the NPU rather than the platform memory map. Each needs evidence this study did
not collect.
