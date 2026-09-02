# The build tree was not stock — found before the pass, not after

The frozen protocol requires a **stock single-inference runner**. That is a claim
about the tree on disk, so it was checked against the tree rather than assumed.

## What the audit found

```
 M source/hal/source/platform/mps4/source/platform_drivers.c
?? source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup
?? source/hal/source/components/npu/ethosu_profiler.c.bak.stall
?? dependencies/core-driver/src/ethosu_driver.c.bak
```

Pre-existing UART logs in `/tmp/c-group` (2026-07-26) show `[ITER]`,
`[OFM_DUMP]`, `[C-GROUP]` markers — a **patched multi-inference runner** was
built in this tree at some point. That is exactly what the protocol forbids.

## The runner is stock; one platform file was not

| file | verdict | evidence |
| --- | --- | --- |
| `UseCaseHandler.cc` | **stock** | matches `HEAD`; no `C-GROUP`/`ITER` markers; sha equals its own `.bak.cgroup` |
| `ethosu_profiler.c` | **stock** | matches `HEAD` |
| `core-driver/ethosu_driver.c` | **stock** | clean at `0356707` |
| `platform_drivers.c` (mps4) | **modified** | 2 lines, tracked |

The modification was a stray declaration:

```c
+int state;          /* file scope */
 #if defined(ARM_NPU)
...
+int state;          /* again, inside platform_init */
-    int state;      /* original local removed */
```

Semantically a no-op — the local shadows the global and `platform_init` behaves
identically — but it changes the linked bytes, and `mps4` is the platform for
**SSE-315 and SSE-320**. Left in place it would have entered all 35 SSE-320/U85
cells, i.e. 35 of the 77 primary-benchmark cells, without appearing anywhere in
the provenance record.

Reverted; the tree is now clean at `b2c0bb2884698b7328f65c41b7c8c51ca9bec386`
with zero tracked modifications. The diff is retained in this directory.

## Why this belongs in the record

The recurring defect in this project has been a **host-side declaration treated
as firmware authority**. This is the same shape: "the runner is stock" was true,
"the tree is stock" was not, and only one of them was checked by the protocol as
written. The build-graph audit that produced BUILD_COUNT=133 read the same tree,
so the check had to run before the pass, not after it.
