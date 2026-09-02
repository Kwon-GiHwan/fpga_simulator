# The deterministic metric vector — fixed before Stage 2 produces a result

Stage 2 tests `M1 == M2`. Which fields carry that equality is defined **here,
before any M2 exists**, so the boundary cannot be drawn around whatever happens
to agree.

## Equality-bearing — exact match required

Simulated output and the identity of what produced it.

```
measurement.status
measurement.inference_count_line
measurement.npu_total_cycles
measurement.npu_active_cycles
measurement.npu_idle_cycles
measurement.axi0_rd_beats
measurement.axi0_wr_beats
measurement.axi1_rd_beats

artifact_identity.model_sha256
artifact_identity.vela_sha256
artifact_identity.generated_cc_body_sha256
artifact_identity.axf_sha256

config_identity.platform
config_identity.npu
config_identity.mac_config
config_identity.fvp
config_identity.timing_adapter_cache
config_identity.embedded_build_stamp
config_identity.source_date_epoch
```

A difference in **any** of these is `DETERMINISM_FAILURE`: Stage 2 stops and
Stage 3 is prohibited. Not averaged, not re-run, not out-voted.

## Not equality-bearing — operational telemetry

These vary by construction and prove nothing about the simulation.

```
measurement.wall_clock_s          host scheduling
measurement.owned_pgid            per-process
measurement.survivors_after_cleanup   checked as a hard stop, not for equality
elapsed_s                         host scheduling
uart_tail                         run-specific evidence text
filesystem paths, timestamps
```

`survivors_after_cleanup` is excluded from *equality* but is still a hard-stop
condition in its own right — it must be empty.

## Membership of the determinism test

The members are exactly `M1`, `M2`, `M3`.

The qualification-pass value is **not** a member and must never be used as a
third opinion to out-vote a disagreeing repetition. A qualification value that
happens to match one of them is a coincidence of a deterministic simulator, not
evidence about the formal set.

## Informational, carried but not compared

```
generated_cc_raw_sha256_informational
```

Carries the generator's wall-clock comment; non-reproducible by construction and
provably absent from the executed binary. Recorded for provenance only.
