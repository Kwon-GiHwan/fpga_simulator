# U85 PMU parser — requalified against captured evidence

Closes the host-side defect recorded in `PMU_CAPTURE_CORRECTION.md` before the
board probe, so the probe can actually evaluate the U85 events it is meant to
inspect. **No frozen FVP stage was re-run or rewritten.**

## The fix is to stop assuming the event set

The previous parser hardcoded AXI names and returned `None` on U85. The
replacement **discovers** whichever counters the profile block emits, so a
generation with different names shows up as *data* rather than as absence:

```
INFO - NPU <name>: <value> <unit>
```

`ETHOSU_PMU_` prefixes (U85) are normalised; U55/U65 names carry none. `TOTAL`,
`ACTIVE`, and `IDLE` are required and their absence raises rather than yielding a
partial record.

## Requalification — read-only, against evidence already captured

Applied to the `uart_tail` retained in the 133-cell executability evidence:

```
executable cells parsed        127 / 127
parse failures                   0
TOTAL == ACTIVE + IDLE       127 / 127
```

The identity is not a coincidence — `ethosu_profiler.c:184-190` derives
`IDLE = npu_total_ccnt - NPU_ACTIVE`, so this is the source-level relationship
confirmed on real output.

Event families, discovered rather than declared:

| family | cells |
| --- | --- |
| `U55_U65_AXI_FAMILY` | 92 |
| `U85_SRAM_EXT_FAMILY` | 35 |

| NPU | emitted event set |
| --- | --- |
| `ethos-u55` | `ACTIVE`, `AXI0_RD_DATA_BEAT_RECEIVED`, `AXI0_WR_DATA_BEAT_WRITTEN`, `AXI1_RD_DATA_BEAT_RECEIVED`, `IDLE`, `TOTAL` |
| `ethos-u65` | identical to U55 |
| `ethos-u85` | `ACTIVE`, `SRAM_RD_DATA_BEAT_RECEIVED`, `SRAM_WR_DATA_BEAT_WRITTEN`, `EXT_RD_DATA_BEAT_RECEIVED`, `EXT_WR_DATA_BEAT_WRITTEN`, `IDLE`, `TOTAL` |

The five U85 memory counters that the old parser dropped are recovered here.

## Mutation tests — 15/15 PASS

A parser that cannot fail would repeat the original defect.

| test | requirement |
| --- | --- |
| `P1` U85 five events captured, `EXT_WR` = 36 | positive |
| `P2` family classification U85 / U55 | positive |
| `P3` `TOTAL == ACTIVE + IDLE` both families | positive |
| `P4` `ETHOSU_PMU_` prefix normalised, raw name retained | positive |
| `N1` no profile block | **raises** |
| `N2` `TOTAL` absent | **raises** |
| `N3` `ACTIVE` absent | **raises** |
| `N4` block with no counters | **raises** |
| `N5` duplicated counter | **raises** |
| `N6` `IDLE` off by one | identity violation **detected** |
| `N7` all-zero record | parses, `TOTAL == 0` **visible**; a zero auxiliary count is **not** an error |

`N7` matters for the board probe: a zero auxiliary event is legitimate and must
not auto-fail, while `TOTAL == 0` must remain visible as the disqualifying
condition.

## Scope

This qualifies the parser only. The frozen 222-sample FVP evidence is unchanged
and still lacks the U85 memory counters, because those stage records retained
parsed fields rather than raw UART. Recovering them into the formal dataset would
require re-acquisition against a frozen artifact — a decision, not an action.
