#!/usr/bin/env python3
"""Assemble the P0-E analysis view: for each cell, link the frozen P0-D
clean/debug/verbose evidence with the P0-D2 v3 profiled records.
Read-only over both evidence trees; the view is a directory of copies."""
import json, os, shutil, sys
sys.path.insert(0, "/tmp")
from insert_irq import decode_cms, parse_payload, CMD0, OP_LAUNCH
from ethosu.vela.tflite.Model import Model

def launch_list(art):
    m = Model.GetRootAsModel(open(art, "rb").read(), 0)
    sg = m.Subgraphs(0)
    for i in range(sg.OperatorsLength()):
        oc = m.OperatorCodes(sg.Operators(i).OpcodeIndex())
        if oc.CustomCode() and b"ethos-u" in oc.CustomCode().lower():
            t = sg.Tensors(sg.Operators(i).Inputs(0))
            pay = bytes(m.Buffers(t.Buffer()).DataAsNumpy().tobytes())
            _, _, cms, _ = parse_payload(pay)
            out, off = [], 0
            for c, o, _, _ in decode_cms(cms):
                if c == 0 and CMD0[o] in OP_LAUNCH:
                    out.append([off, CMD0[o].replace("CMD0_OPCODE_NPU_OP_", "")])
                off += 4 if c == 0 else 8
            return out

PD, PD2, V = "/work/u85mech/pd", "/work/u85mech/pd2", "/work/u85mech/view"
MODELS = ["rnnoise_INT8", "vww4_128_128_INT8", "yolo-fastest_192_face_v4",
          "kws_micronet_m", "ad_medium_int8", "dnn_s_quantized"]
LABELS = ["256_Low", "512_Mid512", "512_Low"]
shutil.rmtree(V, ignore_errors=True)
for m in MODELS:
    for l in LABELS:
        cell = "%s__%s" % (m, l)
        s, s2, d = os.path.join(PD, cell), os.path.join(PD2, cell), os.path.join(V, cell)
        os.makedirs(d)
        shutil.copy2(os.path.join(s, "debug.xml"), d)
        os.makedirs(os.path.join(d, "vela_verbose"))
        shutil.copy2(os.path.join(s, "vela_verbose", "verbose.log"),
                     os.path.join(d, "vela_verbose"))
        shutil.copy2(os.path.join(s, "clean.run1.json"), d)
        art = "/work/u85mech/artifacts/%s/%s_vela.tflite" % (cell, m)
        json.dump(launch_list(art), open(os.path.join(d, "launches.json"), "w"))
        if os.path.isdir(s2):  # v3 profiled arm
            meta = json.load(open(os.path.join(s2, "instr.meta.json")))
            meta["profiled"] = "OK"
            json.dump(meta, open(os.path.join(d, "instr.meta.json"), "w"))
            shutil.copy2(os.path.join(s2, "prof.run1.json"), d)
        else:                  # dnn_s: clean only
            json.dump({"profiled": "NOT_AVAILABLE",
                       "reason": "shape_signature (CPU-op container)"},
                      open(os.path.join(d, "instr.meta.json"), "w"))
print("view assembled:", V)
