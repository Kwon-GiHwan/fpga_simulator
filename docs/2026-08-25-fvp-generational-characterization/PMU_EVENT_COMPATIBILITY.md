# PMU event compatibility across Ethos-U55 / U65 / U85

Mandatory pre-sweep audit. **Result: the PMU event space is not common across
generations, and a cross-generation "same metric" assumption does not hold.**

## Authority

| | |
| --- | --- |
| source | `dependencies/core-driver/include/pmu_ethosu.h` |
| core-driver version | **25.11** |
| structure | two separate `enum ethosu_pmu_event_type` definitions, under `#if defined(ETHOSU55) \|\| defined(ETHOSU65)` and `#elif defined(ETHOSU85)` |

The header's own caveat, quoted:

> *"These values are symbolic. Actual HW-values may change. I.e. always use API
> to set/get actual event-type value."*

**No header or vendor file examined asserts semantic equivalence of any event
across generations.** That absence is the basis for most of the `UNVERIFIED`
classifications below — it is not an oversight to be filled in by assumption.

## The shape of the problem

| | count |
| --- | --- |
| U55/U65 events | **74** |
| U85 events | **171** |
| names present in both | **22** |
| U55/U65 only | 52 |
| U85 only | 149 |
| **shared names whose enum ordinal differs** | **18 of 22** |

Two consequences:

1. **Never compare by event number.** A hardcoded event ID selects a *different
   event* on a different generation. Only symbolic names may cross a generation
   boundary, and only where classified below as usable.
2. **The memory interface was renamed.** U55/U65 expose 33 `AXI0_*`/`AXI1_*`
   events; U85 exposes 39 `EXT0_*`/`EXT1_*` plus `SRAM0_*`, and retains only the
   7 shared `AXI_LATENCY_*` events.

## Classification

### COMMON_SEMANTICS

Shared name, identical ordinal, architecture-neutral definition, no evidence of
redefinition. These are the only events for which a cross-generation metric is
proposed at all.

| event | ordinal | note |
| --- | --- | --- |
| `ETHOSU_PMU_CYCLE` | 1 both | a cycle count; the least architecture-dependent quantity available |
| `ETHOSU_PMU_NPU_IDLE` | 2 both | top-level activity state |
| `ETHOSU_PMU_CC_STALLED_ON_BLOCKDEP` | 3 both | top-level stall |

Even here, "common semantics" means *no evidence of divergence*, not a vendor
guarantee. Cross-generation use is admissible **normalized**, never as absolute
cycles — the version-skew prohibition applies independently.

### GENERATION_SPECIFIC

Present in one generation only, or renamed such that no cross-generation metric
exists without a mapping nobody has asserted.

| group | U55/U65 | U85 |
| --- | --- | --- |
| memory interface | `AXI0_*`, `AXI1_*` (33) | `EXT0_*`, `EXT1_*`, `SRAM0_*` (39+) |
| MAC precision breakdown | `MAC_ACTIVE_8BIT`, `_16BIT`, `_32BIT` | absent |
| MAC stall decomposition | `MAC_STALLED_BY_WD`, `_BY_WD_ACC` | `MAC_STALLED_BY_W`, `_BY_W_OR_ACC` |
| AO stall decomposition | `AO_STALLED_BY_ACC`, `_OFMP`, `_IB` | `AO_STALLED_BY_BS`, `_OB`, `_AB`, `_CB` |
| ECC | `ECC_SB1`, `ECC_DMA` | `ECC_AO_*`, `ECC_MAC_*` (finer) |

The stall decompositions are the clearest case: the *set of things a MAC can
stall on* differs, which is a microarchitectural difference, not a renaming.
Aggregating them into one "stall cycles" metric would compare different
partitions of different pipelines.

### UNVERIFIED

Shared name, but the ordinal differs and no authority states the definitions
coincide. Usable **within** a generation; not comparable across one without
evidence that does not currently exist.

`NPU_ACTIVE` · `MAC_ACTIVE` · `MAC_DPU_ACTIVE` · `MAC_STALLED_BY_ACC` ·
`MAC_STALLED_BY_IB` · `AO_ACTIVE` · `AO_STALLED_BY_OB` · `WD_ACTIVE` ·
`WD_STALLED` · `WD_STALLED_BY_WD_BUF` · `AXI_LATENCY_{ANY,32,64,128,256,512,1024}` ·
`ECC_DMA`

`NPU_ACTIVE` deserves a note: it is the one MLEK actually reads, it is shared by
name, and it is intuitively "the NPU was busy". It is nonetheless `UNVERIFIED`
because U85 decomposes activity differently and no source states the two count
the same cycles. Promoting it on plausibility is the move this project refuses.

## Practical consequence for the sweep

MLEK's default PMU selection **cannot be collected identically across
generations**:

| MLEK event | U55/U65 | U85 |
| --- | --- | --- |
| `NPU_ACTIVE` | yes | yes |
| `CYCLE` | yes | yes |
| `SRAM_RD_DATA_BEAT_RECEIVED` | **NO** | yes |
| `SRAM_WR_DATA_BEAT_WRITTEN` | **NO** | yes |
| `EXT_RD_DATA_BEAT_RECEIVED` | **NO** | yes |
| `EXT_WR_DATA_BEAT_WRITTEN` | **NO** | yes |

So the memory-bandwidth half of the intended metric set is **U85-only as
configured**. On U55/U65 the analogous counters are `AXI0_*`/`AXI1_*`, and using
them as "the same metric" requires a mapping this audit could not source.

### What this forces

- **Cross-generation memory-bandwidth comparison from PMU counters:
  not admissible** as currently sourced. Either restrict memory analysis to
  Vela's estimates — which *are* uniformly defined across configs — or obtain an
  authoritative U55/U65 ↔ U85 counter mapping and re-classify.
- **Vela estimates become the cross-generation memory metric.**
  `cycles_sram_access`, `cycles_dram_access` and the `*_bytes` columns are
  produced by one tool with one definition for every accelerator config, so they
  are internally consistent across generations in a way the PMU counters are not.
  They remain estimates and are labelled as such.
- **PMU counters are for within-generation analysis** and for the Corstone-320
  board validation, where only U85 is involved and the question is FVP-versus-
  hardware rather than generation-versus-generation.

## Re-audit trigger

If the core-driver version changes, this audit is void and must be re-run. The
enum is version-specific and the header says so.
