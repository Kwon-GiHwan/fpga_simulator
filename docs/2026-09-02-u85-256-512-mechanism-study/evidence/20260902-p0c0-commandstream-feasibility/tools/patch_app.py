#!/usr/bin/env python3
"""C0-4 temporary app instrumentation: print CRC32 of each output tensor.
Uses only stock accessors already used unconditionally in this file.
Apply/revert with backup, like patch-driver.py."""
import shutil, sys
from pathlib import Path

F = Path("/opt/arm/ml-embedded-evaluation-kit/source/app/use_case/inference_runner/src/UseCaseHandler.cc")
B = F.with_suffix(".cc.bak.c04")
ANCHOR = "    profiler.PrintProfilingResult();"
BLOCK = """
    { /* C04 OUTPUT CRC - temporary PoC instrumentation, reverted after build */
        for (size_t i = 0; i < model.GetNumOutputs(); ++i) {
            auto c04Tensor = model.GetOutputTensor(i);
            const uint8_t* c04Data = c04Tensor->GetData<uint8_t>();
            uint32_t c04Crc = 0xFFFFFFFFu;
            for (size_t j = 0; j < c04Tensor->Bytes(); ++j) {
                c04Crc ^= c04Data[j];
                for (int k = 0; k < 8; ++k) {
                    c04Crc = (c04Crc >> 1) ^ (0xEDB88320u & (0u - (c04Crc & 1u)));
                }
            }
            info("C04_OUTPUT_CRC[%u]: bytes=%u crc32=0x%08X\\n",
                 (unsigned)i, (unsigned)c04Tensor->Bytes(), ~c04Crc);
        }
    }
"""

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--revert":
        if B.exists():
            shutil.copy2(B, F)
            print("reverted from", B)
        else:
            print("no backup; nothing to revert")
        return
    content = F.read_text()
    if "C04 OUTPUT CRC" in content:
        print("already applied")
        return
    n = content.count(ANCHOR)
    if n != 1:
        raise SystemExit("STOP: anchor count %d != 1" % n)
    shutil.copy2(F, B)
    F.write_text(content.replace(ANCHOR, ANCHOR + BLOCK))
    print("applied; backup:", B)

main()
