# U85 baseline binding — P0-A-D

What the frozen U85 formal MAC sweep actually used, read from frozen evidence
in this repository (not guessed, not from memory). The mechanism study must
either match this or declare a registered departure.

## Frozen sweep identity (per-cell authority: `docs/paper/analysis/canonical_cells.csv`)

| field | value | authority |
| --- | --- | --- |
| platform | SSE-320 (`FVP_Corstone_SSE-320`) | canonical_cells.csv |
| accelerator | `ethos-u85-{128,256,512,1024,2048}` | canonical_cells.csv / vela_matrix.csv |
| memory mode | `Dedicated_Sram` (all U85 cells) | vela_matrix.csv `--memory-mode` |
| timing adapter | ON (required for primary universe) | canonical_cells.csv + `ta_eligibility_contract` in FORMAL_PRESWEEP_ANCHOR.json |
| Vela | 5.0.0, `--config scripts/vela/default_vela.ini --optimise Performance` | vela_matrix.csv `vela_args` |
| MLEK | `26.03-8-gb2c0bb2`, 0 tracked modifications | frozen source closure |
| core-driver | 25.11 | dependency pin |
| Fast Models | 11.27.25 (SSE-320) | MEASUREMENT_SEMANTICS.md |
| FVP MAC parameter | `mps4_board.subsystem.ethosu.num_macs` (SSE-320 path) | stage1.py:63 |
| `extra_args` | empty, recorded per run ("reserved for future use") | MEASUREMENT_SEMANTICS.md |
| build contract | `SOURCE_DATE_EPOCH=1776763519`, canonical path `/tmp/xq/<cell_id>/build-a1`, arena 2 MiB, embedded literal `Build date: Apr 21 2026 @ 09:25:19` | FORMAL_PRESWEEP_ANCHOR.json `reproducible_build_contract` |
| per-cell artifact ids | model SHA / Vela SHA / AXF SHA columns | canonical_cells.csv |

## Finding 1 — the Vela system-config is MAC-dependent

Exact `vela_args` recorded in the frozen matrix (rnnoise shown; the pattern
holds for every U85 model):

```
256: --accelerator-config ethos-u85-256 --system-config Ethos_U85_SYS_DRAM_Low
     --memory-mode Dedicated_Sram --optimise Performance          (clock 500 MHz)
512: --accelerator-config ethos-u85-512 --system-config Ethos_U85_SYS_DRAM_Mid_512
     --memory-mode Dedicated_Sram --optimise Performance          (clock 1 GHz)
```

Full mapping: 128/256 → `SYS_DRAM_Low` (500 MHz assumption); 512 →
`SYS_DRAM_Mid_512`; 1024 → `SYS_DRAM_Mid_1024`; 2048 → `SYS_DRAM_High_2048`
(all 1 GHz). Authority: `vela_matrix.csv` columns `system_config`,
`vela_core_clock`.

Consequence: in the frozen data the 256→512 step changes **MAC count and Vela
system-config together**. The system-config feeds Vela's performance model and
potentially its scheduling; whether it also alters the generated command
stream is precisely a mechanism-study question (Q2), not something to assume
either way.

Two admissible bindings for the mechanism study — **one must be chosen and
registered at P0-B, before any new data**:

- **B-frozen**: reproduce the frozen convention (`Low`@256, `Mid_512`@512).
  Investigates the boundary exactly as the paper observed it; carries the
  config change inside the single variable.
- **B-held**: hold `--system-config` fixed across 256/512 (choice of which
  one is itself a registered decision). Isolates the MAC variable in the
  compiler input; departs from the frozen observation and must be reported as
  a registered departure, never silently substituted.

This document records the fact; it does not choose.

## Finding 2 — whole-model reversal in the frozen data

At this baseline, the frozen canonical cycles show exactly **one** 256→512
whole-model regression:

```
rnnoise_INT8        36,086 → 55,086   (+19,000)   REGRESSES
kws / ad / vww4 / yolo / mobilenet / wav2letter    all improve
```

Vela estimates predict improvement for all seven (rnnoise included), so the
rnnoise reversal is also a Vela↔FVP disagreement point. The mechanism-study
premise that VWW/OD also regress does **not** hold in this frozen baseline; if
that premise comes from a different study (different memory mode/platform),
the workload groups in P0-B must be re-derived from whichever dataset the
study is actually about. Flagged for the registration decision.

## Finding 3 — DNN-S availability

`dnn_s_quantized` has U85 Vela artifacts in the container resources
(`dnn_s_quantized_vela_Z256.tflite`,
`dnn_s_quantized_summary_Ethos_U85_SYS_DRAM_Low_Z256.csv`) but sits outside
the frozen 7-workload universe (9.5 % CPU operators; excluded from scaling
analysis by the frozen matrix contract). Admission would need a registered
justification and separate reporting; default per the frozen contract is
`NOT_AVAILABLE` for pooled analysis.

## Existing U85 build directories (container, unaudited identity)

`build-prof-u85-{128,256,512,1024,2048}` and `build-prof-u85-256-new` exist in
the MLEK root. None has been identity-checked against the frozen build
contract; `-new` in particular is an unexplained variant. The mechanism study
builds its own artifacts under its own namespace rather than reusing these,
unless a hash check proves one identical to a frozen-contract build.
