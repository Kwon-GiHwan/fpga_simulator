# MLEK build graph audit — the runner is workload-bound

**Frozen build count: 133, not 19.**

## The question

Two runners built for the *same* configuration (SSE-320 / U85 / Z1024) differ:

```
wav2letter  bf336fb42568efeb…
rnnoise     f4cd7a9dfb90bb5a…
```

If the runner were configuration-bound, one build per configuration would serve
all seven workloads and the sweep would need **19** builds. If it is
workload+configuration-bound, it needs **133**.

## The answer, from real build inputs

The model is **compiled into the binary**. MLEK's `gen_utils.py` emits the vela
artifact as a C byte array and links it:

```
build-qual-320-u85-1024/generated/inference_runner/src/wav2letter_pruned_int8_vela.tflite.cc
build-qual-320-u85-1024-rnnoise/generated/inference_runner/src/rnnoise_INT8_vela.tflite.cc
```

The sizes carry the proof:

| | vela artifact | generated `.cc` | linked `.axf` |
| --- | --- | --- | --- |
| `wav2letter` | 14,495,424 B | 87,426,274 B | **18,270,508 B** |
| `rnnoise` | 126,416 B | 763,185 B | **3,901,488 B** |

The 14.4 MB binary difference is the model weights. The model is not loaded at
runtime; `inference_runner_MODEL_PATH` is a **build input**.

```
BUILD_COUNT = 7 workloads × 19 configurations = 133
```

Measured build time ≈ 47–50 s each → **≈ 1.8 h** of build wall-clock, plus disk
for 133 binaries ranging 3.9–18.3 MB (order 1–2 GB).

Assuming 19 would have produced 19 binaries each containing the wrong model for
6 of its 7 intended cells — and every one of them would have run and reported
plausible numbers.
