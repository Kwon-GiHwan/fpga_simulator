# Reproducible formal re-baseline — 74/74 closed

```
FORMAL_FVP_SAMPLES        0
runtime                   1.07 h
unexpected nondeterminism 0
```

| condition | result |
| --- | --- |
| Representative A/B (U55, U65, U85) | **3/3 PASS** |
| Formal-reference cells | **74/74** |
| Vela SHA: formal == frozen qualification | **74/74** |
| Generated `.cc` BODY SHA pinned | **74/74** |
| Formal AXF reference recorded | **74/74** |
| Embedded build literal == pinned epoch | **74/74** |
| `timing_adapter` = ON | **74/74** |
| `SOURCE_DATE_EPOCH` = 1776763519 | **74/74** |
| Canonical build path honoured | **74/74** |
| Transform identity — distinct values | **1** (`9bed7620e5571be3…`) |

## Collision checks

```
distinct formal AXF references     74 / 74
duplicate AXF references            0
distinct generated .cc BODY hashes 74
```

No two cells share an AXF. A duplicate would have meant two cells carrying the
same binary — the "one build, wrong model" failure that the 133 build count was
derived to prevent — so this is checked rather than assumed.

## Expected inequalities

```
FORMAL_REFERENCE_AXF_SHA256 != EXECUTABILITY_AXF_SHA256     74/74
FORMAL_GENERATED_CC_RAW_SHA256 != EXECUTABILITY_..._RAW      74/74
```

Both are **expected, not defects**. The qualification artifacts carry wall-clock
timestamps; the formal artifacts are built under the pinned epoch. The two
identities are kept side by side rather than one overwriting the other.

## Anchor

```
paper-fvp-formal-presweep-anchor
ANCHOR_DIGEST  5dae05d24d0e3fd87a7a4b964693c52b284055a47a7061046f40ea1efd40d8ef
supersedes     eb3abec46147cc53…  (SUPERSEDED BEFORE FORMAL DATA)
status         FROZEN
```

See `ANCHOR_SUPERSESSION.md`. The anchor is frozen: a further missing field is a
STOP, not an amendment.

Binding: `E_primary = 74`, formal target 222, the 133-cell executability evidence
digests, the formal harness digests, MLEK commit + 9 dependency pins + 4 target
closure identities, the reproducible-build contract, the generated-`.cc`
transform identity, the arena retry contract, the TA eligibility contract, the
scaling contract, the A/B gate, and the canonical 74-cell order with every
per-cell hash.

## Stage 1 gate, per cell, before any FVP runs

```
formal Vela SHA            == anchor formal_vela_sha256
formal .cc BODY SHA        == anchor FORMAL_GENERATED_CC_BODY_SHA256
formal raw AXF SHA         == anchor FORMAL_REFERENCE_AXF_SHA256      (exact)
timing adapter             == ON
```

Only then does the cell run. Stage 2 and Stage 3 use this same reference; it is
never refreshed per repetition.
