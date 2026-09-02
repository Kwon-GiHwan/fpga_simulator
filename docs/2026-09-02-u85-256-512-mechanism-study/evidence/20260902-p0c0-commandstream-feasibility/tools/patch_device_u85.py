#!/usr/bin/env python3
"""C0-4 device-side adaptation: clear the U85 IRQ history alongside clear_irq.

Authority: ethosu85_interface.h cmd_r.clear_irq_history[31:16] ("Clears the
IRQ history mask") paired with status_r.irq_history_mask[31:16] and
npu_op_irq_t.mask[31:16]. Stock streams carry no NPU_OP_IRQ, so for them this
write clears nothing; it is still applied/reverted around builds only.
"""
import shutil, sys
from pathlib import Path

F = Path("/opt/arm/ml-embedded-evaluation-kit/dependencies/core-driver/src/ethosu_device_u85.c")
B = F.with_suffix(".c.bak.c04")
ANCHOR = """    cmd.word           = dev->reg->CMD.word & NPU_CMD_PWR_CLK_MASK;
    cmd.clear_irq      = 1;
    dev->reg->CMD.word = cmd.word;"""
REPL = """    cmd.word              = dev->reg->CMD.word & NPU_CMD_PWR_CLK_MASK;
    cmd.clear_irq         = 1;
    cmd.clear_irq_history = 0xFFFFu; /* C04: release NPU_OP_IRQ halt (no-op for stock streams) */
    dev->reg->CMD.word = cmd.word;"""

if len(sys.argv) > 1 and sys.argv[1] == "--revert":
    if B.exists():
        shutil.copy2(B, F); print("reverted device_u85")
    else:
        print("no backup")
    sys.exit(0)
c = F.read_text()
if "C04: release" in c:
    print("already applied"); sys.exit(0)
if c.count(ANCHOR) != 1:
    raise SystemExit("STOP: device anchor count %d != 1" % c.count(ANCHOR))
shutil.copy2(F, B)
F.write_text(c.replace(ANCHOR, REPL))
print("applied device_u85 history-clear")
