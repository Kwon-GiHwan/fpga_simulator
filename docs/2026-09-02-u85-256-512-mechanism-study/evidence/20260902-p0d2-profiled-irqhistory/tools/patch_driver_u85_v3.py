#!/usr/bin/env python3
"""P0-D profiled-arm instrumentation v3: IRQ-history attribution.

v2's positional record->launch mapping breaks when consecutive NPU_OP_IRQs
are serviced together (small ops; observed 48 IRQs -> 17 records on
rnnoise). U85 provides the exact mechanism to recover attribution:
NPU_OP_IRQ's 16-bit mask ORs into STATUS.irq_history_mask[31:16]
(ethosu85_interface.h status_r L3548), cleared via
CMD.clear_irq_history[31:16] (cmd_r L3714). With one-hot params
(1 << (seq % 16)) each record's history names exactly the launches it
covers; the completion record captures the final merge window.
"""
import shutil
import sys
from pathlib import Path

F = Path("/opt/arm/ml-embedded-evaluation-kit/dependencies/core-driver/src/ethosu_driver.c")
B = F.with_suffix(".c.bak")

DEFS = r'''
/******************************************************************************
 * P0-D per-layer profiling v3 (NPU_OP_IRQ + irq-history attribution).
 * Temporary; reverted after each build. printf after inference end only.
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
    uint32_t hist;   /* STATUS.irq_history_mask consumed by this record */
} plprof_entry_t;

static plprof_entry_t s_plprof[PLPROF_MAX_LAYERS];
static volatile uint32_t s_plprof_count = 0;
static volatile uint32_t s_plprof_final_hist = 0;

void ethosu_profiling_reset(void)
{
    s_plprof_count = 0;
    s_plprof_final_hist = 0;
}

void ethosu_profiling_print(void)
{
    printf("PLPROF_BEGIN,%" PRIu32 "\n", s_plprof_count);
    for (uint32_t i = 0; i < s_plprof_count; i++)
    {
        printf("PLPROF,%" PRIu32 ",%" PRIu64 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",0x%04" PRIX32 "\n",
               i, s_plprof[i].ccnt, s_plprof[i].evt[0], s_plprof[i].evt[1],
               s_plprof[i].evt[2], s_plprof[i].evt[3], s_plprof[i].evt[4],
               s_plprof[i].hist);
    }
    printf("PLPROF_FINAL_HIST,0x%04" PRIX32 "\n", s_plprof_final_hist);
    printf("PLPROF_END\n");
}
'''

NEW_IRQ_HANDLER = r'''void __attribute__((weak)) ethosu_irq_handler(struct ethosu_driver *drv)
{
    if (drv->job.result == ETHOSU_JOB_RESULT_TIMEOUT)
    {
        (void)ethosu_dev_handle_interrupt(&drv->dev);
        return;
    }
    // STATUS: bit5 cmd_end_reached; [31:16] irq_history_mask (U85).
    uint32_t status = ETHOSU_PMU_Get_STATUS(drv);
    bool cmd_end = (status >> 5) & 1;
    uint32_t hist = status >> 16;
    if (!cmd_end)
    {
        if (s_plprof_count < PLPROF_MAX_LAYERS)
        {
            uint32_t idx = s_plprof_count;
            s_plprof[idx].ccnt = ETHOSU_PMU_Get_CCNTR(drv);
            for (uint32_t c = 0; c < 5; c++)
            {
                s_plprof[idx].evt[c] = ETHOSU_PMU_Get_EVCNTR(drv, c);
            }
            s_plprof[idx].hist = hist;
            s_plprof_count++;
        }
        ETHOSU_PMU_CYCCNT_Reset(drv);
        ETHOSU_PMU_EVCNTR_ALL_Reset(drv);
        // Clear IRQ and exactly the consumed history bits.
        ETHOSU_PMU_Clear_IRQ_History(drv, hist);
        return; // inference still running
    }
    s_plprof_final_hist = hist;
    drv->job.state  = ETHOSU_JOB_DONE;
    drv->job.result = ethosu_dev_handle_interrupt(&drv->dev) ? ETHOSU_JOB_RESULT_OK : ETHOSU_JOB_RESULT_ERROR;
    ethosu_semaphore_give(drv->semaphore);
}'''

# helper added to ethosu_pmu.c-adjacent surface is overkill; implement the
# clear inline in the driver via the device function used by the stock path.
# ethosu_dev_handle_interrupt clears clear_irq only; for mid-stream we need
# clear_irq + clear_irq_history. Provide a small device-level helper through
# a declared extern implemented by patching the device file (see
# patch_device_u85_v3 block below applied by this same script).
HELPER_DECL = "void ETHOSU_PMU_Clear_IRQ_History(struct ethosu_driver *drv, uint32_t mask);\n"

DEVICE = Path("/opt/arm/ml-embedded-evaluation-kit/dependencies/core-driver/src/ethosu_device_u85.c")
DEVICE_BAK = DEVICE.with_suffix(".c.bak.v3")
DEVICE_HELPER = r'''
/* P0-D v3 helper: clear IRQ + the given history bits (temporary). */
#include "ethosu_driver.h"
void ETHOSU_PMU_Clear_IRQ_History(struct ethosu_driver *drv, uint32_t mask)
{
    struct ethosu_device *dev = &drv->dev;
    struct cmd_r cmd;
    cmd.word                  = dev->reg->CMD.word & NPU_CMD_PWR_CLK_MASK;
    cmd.clear_irq             = 1;
    cmd.clear_irq_history     = mask & 0xFFFFu;
    dev->reg->CMD.word = cmd.word;
}
'''

WAIT_ANCHOR = "        ethosu_inference_end(drv, drv->job.user_arg);"
WAIT_INSERT = "\n        ethosu_profiling_print();\n        ethosu_profiling_reset();\n"
IRQ_SIG = "void __attribute__((weak)) ethosu_irq_handler(struct ethosu_driver *drv)"
IRQ_END = "    ethosu_semaphore_give(drv->semaphore);\n}"


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--revert":
        for f, b in ((F, B), (DEVICE, DEVICE_BAK)):
            if b.exists():
                shutil.copy2(b, f)
                print("reverted", f.name)
        return
    c = F.read_text()
    if "profiling v3" in c:
        print("driver already applied")
    else:
        i = c.find(IRQ_SIG)
        j = c.find(IRQ_END, i)
        if i == -1 or j == -1 or c.count(WAIT_ANCHOR) != 1:
            raise SystemExit("STOP: driver anchors not found")
        shutil.copy2(F, B)
        out = c[:i] + DEFS + HELPER_DECL + NEW_IRQ_HANDLER + c[j + len(IRQ_END):]
        out = out.replace(WAIT_ANCHOR, WAIT_ANCHOR + WAIT_INSERT)
        F.write_text(out)
        print("applied driver v3")
    d = DEVICE.read_text()
    if "P0-D v3 helper" in d:
        print("device helper already applied")
    else:
        shutil.copy2(DEVICE, DEVICE_BAK)
        DEVICE.write_text(d + DEVICE_HELPER)
        print("applied device v3 helper")


main()
