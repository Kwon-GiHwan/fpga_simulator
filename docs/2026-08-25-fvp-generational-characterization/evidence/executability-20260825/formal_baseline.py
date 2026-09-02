"""Reproducible formal AXF re-baseline for the 74 primary cells.

Identity = pinned source closure + pinned toolchain + pinned SOURCE_DATE_EPOCH
         + pinned deterministic build path + pinned build arguments.

Does not touch the executability AXF digests; those stay as historical evidence.
"""
import json, os, shutil, subprocess, sys, time

sys.path.insert(0, "/tmp/xqbin")
import ccident

KIT = "/opt/arm/ml-embedded-evaluation-kit"
ROOT = "/tmp/xq"
ARENA = 0x00200000
MLEK_COMMIT = "b2c0bb2884698b7328f65c41b7c8c51ca9bec386"
FORMAL_SOURCE_DATE_EPOCH = 1776763519          # commit timestamp of MLEK_COMMIT
EPOCH_AUTHORITY = "MLEK_COMMIT_TIMESTAMP"
EXPECTED_BUILD_DATE = "Apr 21 2026"
EXPECTED_BUILD_TIME = "09:25:19"
FREE_GATE = 1 << 30

MODEL_SRC = {
 "ad_medium_int8": "ad/ad_medium_int8.tflite",
 "kws_micronet_m": "kws/kws_micronet_m.tflite",
 "mobilenet_v2_1.0_224_INT8": "img_class/mobilenet_v2_1.0_224_INT8.tflite",
 "rnnoise_INT8": "noise_reduction/rnnoise_INT8.tflite",
 "vww4_128_128_INT8": "vww/vww4_128_128_INT8.tflite",
 "wav2letter_pruned_int8": "asr/wav2letter_pruned_int8.tflite",
 "yolo-fastest_192_face_v4": "object_detection/yolo-fastest_192_face_v4.tflite",
}


def env():
    e = dict(os.environ)
    e["SOURCE_DATE_EPOCH"] = str(FORMAL_SOURCE_DATE_EPOCH)
    return e


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env(), **kw)


def sha256(p):
    return sh("sha256sum %s" % p).stdout.split()[0] if os.path.exists(p) else None


def free_bytes():
    st = os.statvfs("/")
    return st.f_bavail * st.f_frsize


def generated_cc_body_sha(path):
    """Narrow canonical identity: removes exactly the generator's wall-clock
    Date field, asserted against the pinned template grammar. Fails closed."""
    if not path or not os.path.exists(path):
        return None
    return ccident.body_sha256(open(path, "rb").read())


def embedded_build_stamp(axf):
    out = sh("arm-none-eabi-strings %s | grep -m1 'Build date:'" % axf).stdout.strip()
    return out


def build_cell(cell, ws_suffix=""):
    """Build one cell at its canonical path. Returns artifact identities."""
    cid = cell["cell_id"]
    ws = os.path.join(ROOT, cid + ws_suffix)
    shutil.rmtree(ws, ignore_errors=True)
    vdir = os.path.join(ws, "vela")
    os.makedirs(vdir, exist_ok=True)
    src = os.path.join(KIT, "resources_downloaded", MODEL_SRC[cell["model"]])
    vargs = ("vela --accelerator-config %s --config %s/scripts/vela/default_vela.ini "
             "--system-config %s --memory-mode %s --optimise Performance "
             "--output-dir %s %s" % (cell["accelerator_config"], KIT,
                                     cell["system_config"], cell["memory_mode"], vdir, src))
    rv = sh(vargs)
    art = os.path.join(vdir, "%s_vela.tflite" % cell["model"])
    if not os.path.exists(art):
        return {"ok": False, "stage": "vela", "log": (rv.stdout + rv.stderr)[-1200:], "ws": ws}
    bdir = os.path.join(ws, "build-a1")          # canonical, frozen in the contract
    cargs = ("cmake -B %s -S %s "
             "-DCMAKE_TOOLCHAIN_FILE=%s/scripts/cmake/toolchains/bare-metal-gcc.cmake "
             "-DTARGET_PLATFORM=%s -DTARGET_SUBSYSTEM=%s -DETHOS_U_NPU_ID=%s "
             "-DETHOS_U_NPU_CONFIG_ID=%s -DETHOS_U_NPU_MEMORY_MODE=%s -DETHOS_U_NPU_ENABLED=ON "
             "-DUSE_CASE_BUILD=inference_runner -Dinference_runner_ACTIVATION_BUF_SZ=0x%08X "
             "-Dinference_runner_MODEL_PATH=%s"
             % (bdir, KIT, KIT, cell["target_platform"], cell["target_subsystem"],
                cell["npu_id"] if "npu_id" in cell else {"ethos-u55": "U55", "ethos-u65": "U65",
                                                          "ethos-u85": "U85"}[cell["npu"]],
                cell["npu_config_id"], cell["memory_mode"], ARENA, art))
    rc = sh(cargs)
    if rc.returncode != 0:
        return {"ok": False, "stage": "configure", "log": (rc.stdout + rc.stderr)[-1500:], "ws": ws}
    rb = sh("cmake --build %s -j $(nproc)" % bdir)
    axf = os.path.join(bdir, "bin", "mlek_inference_runner.axf")
    if rb.returncode != 0 or not os.path.exists(axf):
        return {"ok": False, "stage": "build", "log": (rb.stdout + rb.stderr)[-1500:], "ws": ws}
    gen = sh("ls %s/generated/inference_runner/src/*_vela.tflite.cc" % bdir).stdout.strip().splitlines()
    gen = gen[0] if gen else None
    ta = sh("grep -E '^ETHOS_U_NPU_TIMING_ADAPTER_ENABLED' %s/CMakeCache.txt" % bdir).stdout.strip()
    return {"ok": True, "ws": ws, "build_dir": bdir, "vela_artifact": art,
            "vela_sha256": sha256(art), "generated_cc": gen,
            "generated_cc_sha256": sha256(gen) if gen else None,
            "generated_cc_body_sha256": generated_cc_body_sha(gen),
            "axf": axf, "axf_sha256": sha256(axf),
            "timing_adapter_cache": ta, "build_args": cargs,
            "embedded_build_stamp": embedded_build_stamp(axf),
            "source_date_epoch": FORMAL_SOURCE_DATE_EPOCH,
            "source_date_epoch_authority": EPOCH_AUTHORITY,
            "mlek_commit": MLEK_COMMIT}


def ab_gate(cells, outdir):
    """One representative per NPU family; A and B must agree on all three."""
    reps, seen = [], set()
    for c in cells:
        if c["npu"] not in seen:
            seen.add(c["npu"]); reps.append(c)
    results = []
    for c in reps:
        a = build_cell(c)                      # canonical path
        a = dict(a); shutil.rmtree(a.get("ws", "/nonexistent"), ignore_errors=True)
        b = build_cell(c)                      # same canonical path, rebuilt
        ok = a.get("ok") and b.get("ok")
        stamp_ok = ok and (EXPECTED_BUILD_DATE in a["embedded_build_stamp"]
                           and EXPECTED_BUILD_TIME in a["embedded_build_stamp"])
        r = {"cell_id": c["cell_id"], "npu": c["npu"], "both_built": bool(ok),
             "vela_match": ok and a["vela_sha256"] == b["vela_sha256"],
             "generated_cc_raw_match": ok and a["generated_cc_sha256"] == b["generated_cc_sha256"],
             "generated_cc_body_match": ok and a["generated_cc_body_sha256"] == b["generated_cc_body_sha256"],
             "axf_match": ok and a["axf_sha256"] == b["axf_sha256"],
             "axf_sha256": a.get("axf_sha256"),
             "embedded_build_stamp": a.get("embedded_build_stamp"),
             "embedded_stamp_matches_epoch": bool(stamp_ok),
             "vela_reproduces_qualification": ok and a["vela_sha256"] == c["qual_vela_sha256"],
             "generated_cc_reproduces_qualification":
                 ok and a["generated_cc_sha256"] == c["qual_generated_cc_sha256"]}
        r["PASS"] = all(r[k] for k in ("both_built", "vela_match", "generated_cc_body_match",
                                       "axf_match", "embedded_stamp_matches_epoch",
                                       "vela_reproduces_qualification"))
        shutil.rmtree(b.get("ws", "/nonexistent"), ignore_errors=True)
        results.append(r)
        print("AB %-46s %s" % (r["cell_id"][:46], "PASS" if r["PASS"] else "FAIL " + json.dumps(r)),
              flush=True)
    json.dump(results, open(os.path.join(outdir, "_AB_GATE.json"), "w"), indent=1)
    return all(r["PASS"] for r in results)


def main():
    cells = json.load(open(sys.argv[1]))
    outdir = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "all"
    os.makedirs(outdir, exist_ok=True)
    if mode in ("ab", "all"):
        if not ab_gate(cells, outdir):
            print("AB_GATE_FAILED"); return 2
        print("AB_GATE_PASS", flush=True)
        if mode == "ab":
            return 0
    for c in cells:
        dest = os.path.join(outdir, "%03d_%s.json" % (c["seq"], c["cell_id"]))
        if os.path.exists(dest):
            continue
        if free_bytes() < FREE_GATE:
            print("HALT_FREE_SPACE at seq %d" % c["seq"]); return 2
        t0 = time.monotonic()
        r = build_cell(c)
        if not r.get("ok"):
            print("STOP seq=%d %s BUILD_FAILED stage=%s" % (c["seq"], c["cell_id"], r.get("stage")))
            json.dump({"cell_id": c["cell_id"], "seq": c["seq"], "error": r},
                      open(os.path.join(outdir, "_STOP.json"), "w"), indent=1)
            return 3
        stamp_ok = (EXPECTED_BUILD_DATE in r["embedded_build_stamp"]
                    and EXPECTED_BUILD_TIME in r["embedded_build_stamp"])
        rec = {"seq": c["seq"], "cell_id": c["cell_id"], "model": c["model"],
               "platform": c["platform"], "npu": c["npu"], "mac_config": c["mac_config"],
               "accelerator_config": c["accelerator_config"], "system_config": c["system_config"],
               "memory_mode": c["memory_mode"], "npu_config_id": c["npu_config_id"],
               "target_platform": c["target_platform"], "target_subsystem": c["target_subsystem"],
               "timing_adapter": c["timing_adapter"], "fvp": c["fvp"],
               "model_sha256": c["model_sha256"],
               "EXECUTABILITY_AXF_SHA256": c["qual_axf_sha256"],
               "FORMAL_REFERENCE_AXF_SHA256": r["axf_sha256"],
               "formal_vela_sha256": r["vela_sha256"],
               "vela_reproduces_qualification": r["vela_sha256"] == c["qual_vela_sha256"],
               "FORMAL_GENERATED_CC_RAW_SHA256": r["generated_cc_sha256"],
               "FORMAL_GENERATED_CC_BODY_SHA256": r["generated_cc_body_sha256"],
               "EXECUTABILITY_GENERATED_CC_RAW_SHA256": c["qual_generated_cc_sha256"],
               "generated_cc_identity_transform": ccident.transform_identity(),
               "canonical_build_path": r["build_dir"],
               "build_args": r["build_args"], "arena": ARENA,
               "timing_adapter_cache": r["timing_adapter_cache"],
               "embedded_build_stamp": r["embedded_build_stamp"],
               "embedded_stamp_matches_epoch": stamp_ok,
               "source_date_epoch": FORMAL_SOURCE_DATE_EPOCH,
               "source_date_epoch_authority": EPOCH_AUTHORITY,
               "mlek_commit": MLEK_COMMIT,
               "elapsed_s": round(time.monotonic() - t0, 1)}
        shutil.rmtree(r["ws"], ignore_errors=True)
        bad = [k for k in ("vela_reproduces_qualification",
                           "embedded_stamp_matches_epoch") if not rec[k]]
        if bad:
            print("STOP seq=%d %s FAILED=%s" % (c["seq"], c["cell_id"], bad))
            json.dump(rec, open(os.path.join(outdir, "_STOP.json"), "w"), indent=1)
            return 3
        json.dump(rec, open(dest, "w"), indent=1)
        print("[%2d/74] %-48s ref=%s %4.0fs" %
              (c["seq"], c["cell_id"][:48], rec["FORMAL_REFERENCE_AXF_SHA256"][:16],
               rec["elapsed_s"]), flush=True)
    print("REBASELINE_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
