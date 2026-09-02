# Harness requalification — PASS, with a negative that actually fires

Requalified on a short known-good cell before the 133-cell pass, per the frozen
requirement. A positive alone is a silent gate, so the requalification also
forces the failure path.

**Cell:** `rnnoise_INT8 / SSE-300 / ethos-u55-32` (0.7 s wall-clock)

| condition | required | observed |
| --- | --- | --- |
| success = count AND marker AND no fatal | all three | `SUCCESS`, count line `1`, marker present, `fatal_marker=null` |
| failure reachable | fatal before completion | `FAILURE_FATAL_BEFORE_COMPLETION`, deficit parsed |
| cleanup | own process group, global scan 0 | `survivors_after_cleanup=[]` on **both** runs |
| global scan after | 0 live | `[]` (6 PIDs present, all `Z` defunct — filtered) |

`PASS = true`.

## The negative had to be forced twice

First attempt used a 4 KiB arena and **still succeeded** — `rnnoise` genuinely
fits. That is a mis-designed negative, not a passing harness, and it would have
left the failure path unproven. Before re-trying, the knob itself was verified:

```
ARENA=0x00200000  activationBuf_size=00200000  axf=445723ecba8b25ca
ARENA=0x00001000  activationBuf_size=00001000  axf=87a578f06742d22f
```

The option is live — it sizes the symbol and changes the binary. At `0x100` the
fatal path fired:

```
TFLM - Failed to resize buffer. Requested: 144, available 132, missing: 12
ERROR - tensor allocation failed!
ERROR - Failed to initialise model
```

## Reproducibility, checked early

The freshly compiled vela artifact reproduced the frozen 2026-08-24 matrix hash
**byte-for-byte** (`vela_sha_matches_frozen: true`). The rebuild-must-reproduce
requirement is therefore already demonstrated on one cell rather than merely
asserted.

## A semantic limit worth stating plainly

The stock runner prints `Total number of inferences: 1` as a **hardcoded string
literal** (`UseCaseHandler.cc:158`), not a counter. Requiring `count == 1` is a
valid *completion* check — execution reached post-inference code — but it is
**not** independent verification of how many inferences ran. With a stock
single-inference runner the two coincide; the check must not be described as
counting.

EXECUTABILITY_QUALIFICATION_RUNS > 0, FORMAL_FVP_SAMPLES = 0.
