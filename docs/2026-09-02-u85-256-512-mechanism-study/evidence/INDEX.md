# Mechanism-study raw evidence — by stage and experiment date

Experiment dates are from server file metadata (mtime,
`gihwan:/home/gihwan/mps4/U85_MECH_*`); git does not preserve mtimes, so
the windows are recorded here. Within each stage: `uart-logs/` raw FVP UART
captures, `run-vectors/` parsed per-run vectors and build identities,
`reports/` campaign reports and analyzer outputs, `vela-debug/` debug-db
XML and verbose-schedule captures, `build-logs/` cmake configure/build
logs, `tools/` the exact scripts run, `manifests/` SHA-256 manifests of the
original archive, `misc/` uncategorized remainders (fvp stdout logs,
launches.json), `binaries.tar.gz` AXF/BIN/tflite/map/generated sources
(mtimes preserved inside the tar).

| stage | UTC window (2026-09-02) | origin archive |
| --- | --- | --- |
| 20260902-p0c0-commandstream-feasibility | 00:19–01:26 | U85_MECH_P0C0_20260902T003028Z |
| 20260902-p0c-profiling-qualification | 01:50–01:57 | U85_MECH_P0C_20260902T015728Z |
| 20260902-p0d-formal-clean | 02:03–02:46 | U85_MECH_P0D_20260902T024627Z |
| 20260902-p0d2-profiled-irqhistory | 02:03–05:16 | U85_MECH_P0D2_20260902T051659Z |
| 20260902-p1a-memory-robustness | 06:17–06:39 | U85_MECH_P1A_20260902T063919Z |

The server archives remain the frozen originals; each stage's
`manifests/EVIDENCE.sha256` verifies file identity against them.
