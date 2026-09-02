#!/usr/bin/env python3
"""P0-C U85 per-layer driver instrumentation, v2.

Differences from the prior study's patch-driver.py (which is preserved
untouched as a prior-study artifact):
  - 5 event-counter slots captured per layer (the stock U85 profiler
    configures CNT1..CNT5 = NPU_ACTIVE, SRAM_RD, SRAM_WR, EXT_RD, EXT_WR),
  - the per-layer table prints via plain printf AFTER inference end, so the
    driver log severity can stay at its default "warning" and no driver INFO
    line is emitted inside the measurement window (Q-B),
  - buffer of 512 entries.
Apply/revert with backup; every application is per-build and reverted.
"""
import shutil
import sys
from pathlib import Path

F = Path("/opt/arm/ml-embedded-evaluation-kit/dependencies/core-driver/src/ethosu_driver.c")
B = F.with_suffix(".c.bak")

DEFS = r'''
/******************************************************************************
 * P0-C per-layer profiling v2 (NPU_OP_IRQ based). Temporary; reverted after
 * each build. Prints via printf after inference end (no in-window logging).
 ******************************************************************************/
#define ETHOSU_PER_LAYER_PROFILING 1
#include "pmu_ethosu.h"
#include <inttypes.h>
#include <stdio.h>

#define PLPROF_MAX_LAYERS 512

typedef struct
{
    uint64_t ccnt;
    uint32_t evt[5];
} plprof_entry_t;

static plprof_entry_t s_plprof[PLPROF_MAX_LAYERS];
static volatile uint32_t s_plprof_count = 0;

void ethosu_profiling_reset(void)
{
    s_plprof_count = 0;
}

void ethosu_profiling_print(void)
{
    printf("PLPROF_BEGIN,%" PRIu32 "\n", s_plprof_count);
    for (uint32_t i = 0; i < s_plprof_count; i++)
    {
        printf("PLPROF,%" PRIu32 ",%" PRIu64 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 "\n",
               i, s_plprof[i].ccnt, s_plprof[i].evt[0], s_plprof[i].evt[1],
               s_plprof[i].evt[2], s_plprof[i].evt[3], s_plprof[i].evt[4]);
    }
    printf("PLPROF_END\n");
}
'''

NEW_IRQ_HANDLER = r'''void __attribute__((weak)) ethosu_irq_handler(struct ethosu_driver *drv)
{
    // Prevent race condition where interrupt triggered after a timeout waiting
    // for semaphore, but before NPU is reset.
    if (drv->job.result == ETHOSU_JOB_RESULT_TIMEOUT)
    {
        (void)ethosu_dev_handle_interrupt(&drv->dev);
        return;
    }
    // STATUS bit 5 = cmd_end_reached (authority: ethosu85_interface.h
    // status_r): 0 = mid-stream NPU_OP_IRQ, 1 = NPU_OP_STOP completion.
    uint32_t status = ETHOSU_PMU_Get_STATUS(drv);
    bool cmd_end = (status >> 5) & 1;
    if (!cmd_end)
    {
        if (s_plprof_count < PLPROF_MAX_LAYERS)
        {
            uint32_t idx = s_plprof_count;
            s_plprof[idx].ccnt   = ETHOSU_PMU_Get_CCNTR(drv);
            for (uint32_t c = 0; c < 5; c++)
            {
                s_plprof[idx].evt[c] = ETHOSU_PMU_Get_EVCNTR(drv, c);
            }
            s_plprof_count++;
        }
        ETHOSU_PMU_CYCCNT_Reset(drv);
        ETHOSU_PMU_EVCNTR_ALL_Reset(drv);
        (void)ethosu_dev_handle_interrupt(&drv->dev);
        return; // inference still running; do not signal the semaphore
    }
    drv->job.state  = ETHOSU_JOB_DONE;
    drv->job.result = ethosu_dev_handle_interrupt(&drv->dev) ? ETHOSU_JOB_RESULT_OK : ETHOSU_JOB_RESULT_ERROR;
    ethosu_semaphore_give(drv->semaphore);
}'''

WAIT_ANCHOR = "        ethosu_inference_end(drv, drv->job.user_arg);"
WAIT_INSERT = "\n        ethosu_profiling_print();\n        ethosu_profiling_reset();\n"

IRQ_SIG = "void __attribute__((weak)) ethosu_irq_handler(struct ethosu_driver *drv)"
IRQ_END = "    ethosu_semaphore_give(drv->semaphore);\n}"


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--revert":
        if B.exists():
            shutil.copy2(B, F)
            print("reverted driver from", B)
        else:
            print("no backup")
        return
    c = F.read_text()
    if "P0-C per-layer profiling v2" in c:
        print("already applied")
        return
    i = c.find(IRQ_SIG)
    if i == -1:
        raise SystemExit("STOP: irq handler signature not found")
    j = c.find(IRQ_END, i)
    if j == -1:
        raise SystemExit("STOP: irq handler end not found")
    if c.count(WAIT_ANCHOR) != 1:
        raise SystemExit("STOP: wait anchor count != 1")
    shutil.copy2(F, B)
    out = c[:i] + DEFS + NEW_IRQ_HANDLER + c[j + len(IRQ_END):]
    out = out.replace(WAIT_ANCHOR, WAIT_ANCHOR + WAIT_INSERT)
    F.write_text(out)
    print("applied driver v2 (5-slot, printf)")


main()
