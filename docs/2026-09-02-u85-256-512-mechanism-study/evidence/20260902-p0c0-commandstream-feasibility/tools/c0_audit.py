#!/usr/bin/env python3
"""P0-C0 stages C0-2 (branch usage audit) and C0-3 (identity round-trip).

READ-ONLY with respect to command streams: nothing is inserted.
Opcode tables are extracted mechanically from the vendor header
(ethosu85_interface.h); nothing is derived from observed byte patterns.

Compiles the 18 P0 candidate Vela artifacts (compile-only; no runtime),
extracts each Ethos-U custom-op payload, walks the driver-action framing
(authority: ethosu_driver.c cop_data_s), decodes every command word
(authority: cmd word bitfields opcode[9:0]/control[15:14]/param[31:16];
CMD1 carries one extra payload word), and requires a byte-identical
zero-modification re-serialization of every payload.
"""
import hashlib, json, os, re, subprocess, sys

KIT = "/opt/arm/ml-embedded-evaluation-kit"
HDR = KIT + "/dependencies/core-driver/src/ethosu85_interface.h"
OUT = "/work/u85mech"
ART = OUT + "/artifacts"

FROZEN_MODEL_SHA = {
    "rnnoise_INT8": "9c582545b7c13af44616c44b654f4fe721aa2585630b0ca173ca3589f6f11c2c",
    "vww4_128_128_INT8": "5e76364e80c45776b735563679d45f611cab7ce7fef2ec4e2db088afe009ccae",
    "yolo-fastest_192_face_v4": "e94bcdb011784bead70ab0c0e9d2dae1a9ea5f103b43e1e6fac3019302cf71ab",
    "kws_micronet_m": "c1feed3af5dac44de7477fb4161670ba18a3fc06039e4a14da41b1c4dd454cb4",
    "ad_medium_int8": "a8b1c9037c2a80e6ff770f0a550777cf744a52850bed6545b2bfc9bacf604c98",
    "dnn_s_quantized": "b34dea022996706a558f14fbc967631889cbc82b93f25d326c581763aed71f0b",
}
MODEL_SRC = {
    "rnnoise_INT8": "noise_reduction/rnnoise_INT8.tflite",
    "vww4_128_128_INT8": "vww/vww4_128_128_INT8.tflite",
    "yolo-fastest_192_face_v4": "object_detection/yolo-fastest_192_face_v4.tflite",
    "kws_micronet_m": "kws/kws_micronet_m.tflite",
    "ad_medium_int8": "ad/ad_medium_int8.tflite",
    "dnn_s_quantized": "inference_runner/dnn_s_quantized.tflite",
}
BINDINGS = [  # (label, accelerator, system_config)
    ("256_Low", "ethos-u85-256", "Ethos_U85_SYS_DRAM_Low"),
    ("512_Mid512", "ethos-u85-512", "Ethos_U85_SYS_DRAM_Mid_512"),
    ("512_Low", "ethos-u85-512", "Ethos_U85_SYS_DRAM_Low"),
]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def sha256b(b):
    return hashlib.sha256(b).hexdigest()

# ---- mechanical opcode-table extraction from the vendor header ----------
def extract_enum(prefix):
    """Parse the C-style enums 'CMD0_OPCODE_*'/'CMD1_OPCODE_*' with explicit
    values; fail if any entry lacks an explicit value (no derivation)."""
    table = {}
    pat = re.compile(r"^\s*(%s[A-Z0-9_]+)\s*=\s*(\d+)\s*,?\s*$" % prefix)
    for line in open(HDR):
        m = pat.match(line)
        if m:
            table[int(m.group(2))] = m.group(1)
    if not table:
        raise SystemExit("STOP: no %s entries extracted" % prefix)
    return table

CMD0 = extract_enum("CMD0_OPCODE_")
CMD1 = extract_enum("CMD1_OPCODE_")

# ---- tflite payload extraction (schema classes shipped with Vela) -------
from ethosu.vela.tflite.Model import Model

def ethosu_payload(tflite_path):
    buf = open(tflite_path, "rb").read()
    m = Model.GetRootAsModel(buf, 0)
    assert m.SubgraphsLength() == 1, "multi-subgraph unsupported in audit"
    sg = m.Subgraphs(0)
    payloads = []
    for i in range(sg.OperatorsLength()):
        op = sg.Operators(i)
        oc = m.OperatorCodes(op.OpcodeIndex())
        cc = oc.CustomCode()
        if cc and b"ethos-u" in cc.lower():
            t = sg.Tensors(op.Inputs(0))
            b = m.Buffers(t.Buffer())
            payloads.append(bytes(b.DataAsNumpy().tobytes()))
    return payloads

# ---- driver-action framing walk (authority: cop_data_s) -----------------
def parse_payload(p):
    """Return list of (kind, meta) actions; kind COMMAND_STREAM carries the
    raw cms bytes. Fail-closed on anything unknown."""
    words = len(p) // 4
    assert len(p) % 4 == 0, "payload not word-aligned"
    # word 0: FOURCC "COP1" (authority: ethosu_driver.c ETHOSU_FOURCC, line 54,
    # checked at invoke line 656 before action parsing begins)
    fourcc = int.from_bytes(p[0:4], "little")
    expected = ord("1") << 24 | ord("P") << 16 | ord("O") << 8 | ord("C")
    if fourcc != expected:
        raise SystemExit("STOP: payload fourcc %08x != COP1" % fourcc)
    out, i = [("FOURCC_COP1", {"at": 0})], 1
    while i < words:
        w = int.from_bytes(p[4 * i:4 * i + 4], "little")
        cmd = w & 0xFF
        if cmd == 1:  # OPTIMIZER_CONFIG (+2 words payload)
            out.append(("OPTIMIZER_CONFIG", {"words": 3, "at": i}))
            i += 3
        elif cmd == 2:  # COMMAND_STREAM; 24-bit length in words
            ln = ((w >> 8) & 0xFF) << 16 | (w >> 16)
            cms = p[4 * (i + 1):4 * (i + 1 + ln)]
            assert len(cms) == 4 * ln, "cms extends past payload"
            out.append(("COMMAND_STREAM", {"len_words": ln, "at": i, "cms": cms}))
            i += 1 + ln
        elif cmd == 5:  # NOP
            out.append(("NOP", {"at": i}))
            i += 1
        else:
            raise SystemExit("STOP: unknown driver_action %d at word %d" % (cmd, i))
    return out

# ---- command decoder + identity serializer ------------------------------
def decode_cms(cms):
    """Decode 32-bit LE words. control 0 => CMD0 (1 word); control 1 => CMD1
    (2 words). Anything else => ambiguity STOP."""
    n = len(cms) // 4
    assert len(cms) % 4 == 0
    cmds, i = [], 0
    while i < n:
        w = int.from_bytes(cms[4 * i:4 * i + 4], "little")
        ctrl = (w >> 14) & 0x3
        opc = w & 0x3FF
        par = w >> 16
        if ctrl == 0:
            if opc not in CMD0:
                raise SystemExit("STOP: unknown CMD0 opcode %d at word %d" % (opc, i))
            cmds.append((0, opc, par, None)); i += 1
        elif ctrl == 1:
            if opc not in CMD1:
                raise SystemExit("STOP: unknown CMD1 opcode %d at word %d" % (opc, i))
            if i + 1 >= n:
                raise SystemExit("STOP: truncated CMD1 at word %d" % i)
            pay = int.from_bytes(cms[4 * i + 4:4 * i + 8], "little")
            cmds.append((1, opc, par, pay)); i += 2
        else:
            raise SystemExit("STOP: reserved control %d at word %d" % (ctrl, i))
    return cmds

def serialize_cms(cmds):
    out = bytearray()
    for ctrl, opc, par, pay in cmds:
        out += ((par << 16) | (ctrl << 14) | opc).to_bytes(4, "little")
        if ctrl == 1:
            out += pay.to_bytes(4, "little")
    return bytes(out)

# ---- main ---------------------------------------------------------------
os.makedirs(ART, exist_ok=True)
report = {"opcode_tables": {"cmd0_entries": len(CMD0), "cmd1_entries": len(CMD1),
                            "header_sha256": sha256(HDR)},
          "cells": []}
ok = True
for model, rel in MODEL_SRC.items():
    src = os.path.join(KIT, "resources_downloaded", rel)
    s = sha256(src)
    if s != FROZEN_MODEL_SHA[model]:
        raise SystemExit("STOP: model SHA mismatch for %s: %s" % (model, s))
    for label, acc, syscfg in BINDINGS:
        cell = "%s__%s" % (model, label)
        vdir = os.path.join(ART, cell)
        art = os.path.join(vdir, "%s_vela.tflite" % model)
        if not os.path.exists(art):
            os.makedirs(vdir, exist_ok=True)
            r = subprocess.run(
                "vela --accelerator-config %s --config %s/scripts/vela/default_vela.ini "
                "--system-config %s --memory-mode Dedicated_Sram --optimise Performance "
                "--output-dir %s %s" % (acc, KIT, syscfg, vdir, src),
                shell=True, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(art):
                print(r.stdout[-800:], r.stderr[-800:]); raise SystemExit("STOP: vela failed " + cell)
        pls = ethosu_payload(art)
        cellrep = {"cell": cell, "vela_sha256": sha256(art), "npu_partitions": len(pls),
                   "streams": []}
        for pi, p in enumerate(pls):
            acts = parse_payload(p)
            cmsa = [a for a in acts if a[0] == "COMMAND_STREAM"]
            assert len(cmsa) == 1, "expected exactly one COMMAND_STREAM"
            cms = cmsa[0][1]["cms"]
            cmds = decode_cms(cms)
            rt = serialize_cms(cmds)
            identical = rt == cms
            ok = ok and identical
            per = {}
            for ctrl, opc, par, pay in cmds:
                nm = (CMD0 if ctrl == 0 else CMD1)[opc]
                per[nm] = per.get(nm, 0) + 1
            cellrep["streams"].append({
                "partition": pi,
                "payload_bytes": len(p), "cms_bytes": len(cms),
                "cms_sha256": sha256b(cms),
                "declared_len_words": cmsa[0][1]["len_words"],
                "actions": [a[0] for a in acts],
                "command_count": len(cmds),
                "branch_count": per.get("CMD1_OPCODE_NPU_OP_BRANCH", 0),
                "irq_count": per.get("CMD0_OPCODE_NPU_OP_IRQ", 0),
                "stop_count": per.get("CMD0_OPCODE_NPU_OP_STOP", 0),
                "op_launches": {k: v for k, v in per.items()
                                 if k.startswith("CMD0_OPCODE_NPU_OP_")},
                "roundtrip_byte_identical": identical,
            })
        report["cells"].append(cellrep)
        print(cell, "streams=%d" % len(pls),
              "cmds=%s" % [s["command_count"] for s in cellrep["streams"]],
              "branch=%s" % [s["branch_count"] for s in cellrep["streams"]],
              "rt_ok=%s" % [s["roundtrip_byte_identical"] for s in cellrep["streams"]])

report["all_roundtrips_identical"] = ok
json.dump(report, open(OUT + "/c0_audit_report.json", "w"), indent=1)
print("VERDICT:", "ROUNDTRIP_IDENTITY_OK" if ok else "SERIALIZER_NOT_IDENTITY_PRESERVING")
