# Paper outline — proposed

The organising constraint: **PMU qualification is subordinate.** V13–V15 justify
the measurement boundary in the main text and nothing more. Their mechanics are
appendix material. The contribution is the characterization, not the
qualification of the instrument used to obtain it.

## 1. Introduction

The problem, the gap, and what this work contributes. RQ1–RQ3 stated.

## 2. Background

Ethos-U NPU family and MAC configurations; the Corstone subsystem generations;
Vela's role as compiler and performance model; FVP as cycle model; the MPS4 FPGA
platform. Related work on NPU characterization and on simulation-versus-hardware
validation.

## 3. Methodology

### 3.1 Platforms and configurations
The 19 verified simulated configurations and the single board configuration
(Corstone-320 / U85 @ 1024 MACs). States plainly that combinations were taken
from installed-tool support rather than from documentation, and which remain
unverified.

### 3.2 Workloads
Seven fully-NPU-placed INT8 models spanning 467× in estimated cycles; why
`dnn_s_quantized` is excluded from scaling analysis.

### 3.3 Metrics and experimental procedure
The three kinds of number — compiler estimate, simulated observation, physical
observation — and the rule that they are never plotted on one axis unlabelled.
Warm-up, repetitions, invalid-run handling, provenance.

### 3.4 Measurement-boundary qualification
**Short.** The chain `internal transition → register visibility → MMIO sampling →
CPU observation`, that only the last link is measured, and that this device
exposes no internal completion timestamp. One paragraph on what V13–V15
established, one on what the campaigns explicitly could not settle. Detail to the
appendix.

## 4. Cross-generation simulation characterization

**RQ1.** Trends across U55/U65/U85 and across Corstone generations, including the
two clean isolations the inventory allows: same-NPU-across-platforms for U55 and
for U65@256. Carries the Fast Models version-skew caveat explicitly — as a stated
threat to validity, not a footnote.

**RQ2.** Scaling with MAC configuration: raw speedup, scaling efficiency,
saturation point, workload and operator sensitivity, memory-related bottlenecks.
This is where the 467× workload range does its work.

## 5. Corstone-320 hardware validation

**RQ3.** The board at its one configuration. Reports ranking preservation,
bottleneck consistency, repeatability, and the direction and magnitude of
FVP-versus-board deviation — as characterization of the gap, not as a verdict of
agreement. States up front that scaling cannot be validated physically because
only 1024 MACs exists.

## 6. Discussion

What the trends mean for deployment; where simulation is a reliable proxy and
where it is not; what the deviation characterization implies for practitioners
sizing an NPU from FVP numbers alone.

## 7. Limitations

Stated rather than minimised:

- FVP version skew confounds cross-generation absolute comparison.
- One physical configuration, so no physical scaling validation.
- All timing is software-visible observation; no internal completion timestamp
  exists on this device.
- Cross-observable absolute comparisons are not admissible; the qualification
  campaigns establish qualitative structural similarity only.
- Vela figures are performance-model estimates at an assumed clock, not
  measurements.
- Workloads are the MLEK set — representative of embedded ML, not exhaustive.

## 8. Conclusion

## Appendices

- **A** — Measurement qualification, V13–V15 in full: designs, negatives, the
  matched-control equivalence argument, and the preregistered outcome tables.
- **B** — Measurement semantics contract: admissible metric names, forbidden
  interpretations, and the admissible-comparison table.
- **C** — Full configuration matrix and per-run provenance.
- **D** — Artifact availability: tags, evidence trees, digests.

## Placement note

V13–V15 consumed most of the engineering effort, and the temptation is to give
them proportional space. They should not get it. In the main text they are §3.4
and part of §7 — they exist so a reader can trust §4 and §5. If a reviewer comes
away remembering the qualification rather than the characterization, the paper is
mis-weighted.
