# Execution semantics for 1 warm-up + 3 measured

## The preferred semantics, and the blocker

The preregistered policy is **one fresh FVP/application session executing four
inferences**: warm-up once, then three measured. A warm-up in a separate FVP
process warms nothing for the next cold process, so that arrangement is rejected.

**Stock `inference_runner` cannot do this.** Its handler runs exactly one
inference, with no loop and no repetition option:

```c
if (!RunInference(model, profiler)) { … }
info("Total number of inferences: 1\n");
```

One FVP process = one inference. The preferred semantics are therefore
**unavailable without a source change** to the application under test.

## PMU semantics — qualified, and they are correct

The per-inference requirement is already satisfied by the profiler, which is why
a looped use case would be sound:

```c
Profiler::StartProfiling()  →  hal_pmu_reset();  capture start counters
Profiler::StopProfiling()   →  capture end counters;  UpdateRunningStats(start, end)
```

Each profiled region **resets the PMU** and reports a **start/end delta**. So if
four inferences ran in one session, each would carry an independent,
reset-correct observation. The requirement is met by construction, not by
assumption.

## Options, for decision

1. **Patch `inference_runner` to loop N inferences.** Small and auditable; PMU
   semantics are already per-inference. It modifies the application under test,
   so the patched source and its digest become part of the frozen provenance.
2. **One inference per FVP process.** Requires abandoning in-session warm-up —
   explicitly rejected — and each process pays full cold-start.
3. **A different use case that already repeats.** Not surveyed; would change the
   application and its reporting.

Option 1 is the only one that delivers the preferred semantics. It is **not**
taken unilaterally: it changes the artifact being measured.

## Exact deterministic agreement

Independent of which option is chosen, the three measured inferences must agree
**exactly**. Disagreement is a hard stop for that configuration, never averaged
or median-filtered: the FVP is deterministic, so self-disagreement means the
harness is wrong, and averaging would conceal exactly that.

## Cleanup must kill the process group, not a recorded PID

A shell-based probe recorded `$!` after backgrounding the FVP and killed that PID
on completion. It reported `CLEANUP_ALIVE_AFTER_KILL=0` and was believed clean.

It was not. The FVP that actually ran had a **different PID** than the one
recorded, and it survived — discovered later at **3 h 15 m of CPU time**, pinning
a core the whole while. The cleanup check passed because it inspected the wrong
process.

```
recorded pid   46002        killed, reported clean
actual FVP     46004        survived 3h15m at ~100% CPU
```

Requirement, tightened:

- Launch in a **new session** (`start_new_session=True` / `setsid`).
- Terminate the **process group** (`killpg(getpgid(pid))`), never a single
  recorded PID.
- Verify cleanup by **scanning for surviving FVP processes**, not by re-checking
  the PID that was killed — a PID-scoped check confirms only that the thing you
  already killed is dead.

In a 399-run sweep this failure mode accumulates: each leak holds a core, and the
harness reports success throughout.
