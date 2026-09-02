#!/usr/bin/env python3
"""P0-D formal U85 256/512 mechanism acquisition orchestrator.

18 cells (6 workloads x {256@Low, 512@Mid512, 512@Low}), each with a clean
and a profiled arm, 3 fresh FVP runs per arm, exact-equality gates.
Fail-closed throughout; progress to stdout (tail -f friendly).
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

KIT = "/opt/arm/ml-embedded-evaluation-kit"
ART = "/work/u85mech/artifacts"
PD = "/work/u85mech/pd"
FVP = "/opt/arm/fvp_installed_320/models/Linux64_GCC-9.3/FVP_Corstone_SSE-320"
AUDIT = json.load(open("/work/u85mech/c0_audit_report.json"))
AUDIT_SHA = {c["cell"]: c["vela_sha256"] for c in AUDIT["cells"]}

MODEL_SRC = {
    "rnnoise_INT8": "noise_reduction/rnnoise_INT8.tflite",
    "vww4_128_128_INT8": "vww/vww4_128_128_INT8.tflite",
    "yolo-fastest_192_face_v4": "object_detection/yolo-fastest_192_face_v4.tflite",
    "kws_micronet_m": "kws/kws_micronet_m.tflite",
    "ad_medium_int8": "ad/ad_medium_int8.tflite",
    "dnn_s_quantized": "inference_runner/dnn_s_quantized.tflite",
}
BINDINGS = [
    ("256_Low", "ethos-u85-256", "Ethos_U85_SYS_DRAM_Low", 256),
    ("512_Mid512", "ethos-u85-512", "Ethos_U85_SYS_DRAM_Mid_512", 512),
    ("512_Low", "ethos-u85-512", "Ethos_U85_SYS_DRAM_Low", 512),
]
EPOCH = "1776763519"


def sh(cmd, **kw):
    env = dict(os.environ, SOURCE_DATE_EPOCH=EPOCH)
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          env=env, **kw)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def stop(msg):
    print("STOP:", msg, flush=True)
    sys.exit(2)


def log(*a):
    print(*a, flush=True)


# ---------- stage 1: artifacts, verbose captures, instrumented models ----
cells = []
for model in MODEL_SRC:
    for label, acc, syscfg, macs in BINDINGS:
        cells.append({"cell": "%s__%s" % (model, label), "model": model,
                      "label": label, "acc": acc, "syscfg": syscfg,
                      "macs": macs})

os.makedirs(PD, exist_ok=True)
for c in cells:
    d = os.path.join(PD, c["cell"])
    os.makedirs(d, exist_ok=True)
    art = os.path.join(ART, c["cell"], "%s_vela.tflite" % c["model"])
    s = sha256(art)
    if s != AUDIT_SHA[c["cell"]]:
        stop("artifact sha drift for %s" % c["cell"])
    c["art"], c["vela_sha"] = art, s

    vd = os.path.join(d, "vela_verbose")
    vlog = os.path.join(vd, "verbose.log")
    if not os.path.exists(vlog):
        shutil.rmtree(vd, ignore_errors=True)
        os.makedirs(vd)
        src = os.path.join(KIT, "resources_downloaded", MODEL_SRC[c["model"]])
        r = sh("vela --accelerator-config %s --config %s/scripts/vela/default_vela.ini "
               "--system-config %s --memory-mode Dedicated_Sram --optimise Performance "
               "--verbose-schedule --verbose-performance --output-dir %s %s > %s 2>&1"
               % (c["acc"], KIT, c["syscfg"], vd, src, vlog))
        va = os.path.join(vd, "%s_vela.tflite" % c["model"])
        if not os.path.exists(va) or sha256(va) != c["vela_sha"]:
            stop("verbose-capture artifact mismatch for %s" % c["cell"])
    c["verbose_log"] = vlog

    instr = os.path.join(d, "instr.tflite")
    marker = os.path.join(d, "instr.meta.json")
    if not os.path.exists(marker):
        r = sh("python3 /tmp/insert_irq.py %s %s --all" % (c["art"], instr))
        if r.returncode != 0:
            meta = {"profiled": "NOT_AVAILABLE",
                    "reason": (r.stdout + r.stderr).strip()[-300:]}
            log("[instr] %s NOT_AVAILABLE: %s" % (c["cell"], meta["reason"][:120]))
        else:
            m = re.search(r"IRQ-ALL x(\d+)", r.stdout)
            meta = {"profiled": "OK", "irq_count": int(m.group(1)),
                    "instr_sha256": sha256(instr)}
            log("[instr] %s IRQs=%d" % (c["cell"], meta["irq_count"]))
        json.dump(meta, open(marker, "w"))
    c["instr_meta"] = json.load(open(marker))
    c["instr"] = instr
log("stage1 done: %d cells" % len(cells))

# ---------- stage 2: builds --------------------------------------------

def build(c, arm, model_path):
    d = os.path.join(PD, c["cell"])
    axf_out = os.path.join(d, "%s.axf" % arm)
    meta_out = os.path.join(d, "%s.build.json" % arm)
    if os.path.exists(meta_out):
        return
    bdir = os.path.join(d, "build-" + arm)
    shutil.rmtree(bdir, ignore_errors=True)
    cfg = ("cmake -B %s -S %s "
           "-DCMAKE_TOOLCHAIN_FILE=%s/scripts/cmake/toolchains/bare-metal-gcc.cmake "
           "-DTARGET_PLATFORM=mps4 -DTARGET_SUBSYSTEM=sse-320 -DETHOS_U_NPU_ID=U85 "
           "-DETHOS_U_NPU_CONFIG_ID=Z%d -DETHOS_U_NPU_MEMORY_MODE=Dedicated_Sram "
           "-DETHOS_U_NPU_ENABLED=ON -DUSE_CASE_BUILD=inference_runner "
           "-Dinference_runner_ACTIVATION_BUF_SZ=0x00200000 "
           "-Dinference_runner_MODEL_PATH=%s"
           % (bdir, KIT, KIT, c["macs"], model_path))
    r = sh(cfg)
    if r.returncode != 0:
        stop("configure failed %s/%s: %s" % (c["cell"], arm, r.stderr[-300:]))
    r = sh("cmake --build %s -j $(nproc)" % bdir)
    axf = os.path.join(bdir, "bin", "mlek_inference_runner.axf")
    if r.returncode != 0 or not os.path.exists(axf):
        stop("build failed %s/%s: %s" % (c["cell"], arm, (r.stdout + r.stderr)[-400:]))
    ta = sh("grep -E '^ETHOS_U_NPU_TIMING_ADAPTER_ENABLED' %s/CMakeCache.txt" % bdir).stdout.strip()
    shutil.copy2(axf, axf_out)
    json.dump({"axf_sha256": sha256(axf_out), "timing_adapter": ta,
               "model_path": model_path, "model_sha256": sha256(model_path)},
              open(meta_out, "w"))
    shutil.rmtree(bdir, ignore_errors=True)
    log("[build] %s/%s %s" % (c["cell"], arm, sha256(axf_out)[:12]))


def patches(*names):
    for n in names:
        r = sh("python3 /tmp/%s" % n)
        if r.returncode != 0:
            stop("patch %s failed: %s" % (n, r.stdout + r.stderr))
        log("[patch]", n, r.stdout.strip()[:80])


def reverts(*names):
    for n in names:
        sh("python3 /tmp/%s --revert" % n)
    ok = True
    pairs = [
        ("dependencies/core-driver/src/ethosu_driver.c",
         "dependencies/core-driver/src/ethosu_driver.c.bak"),
        ("source/app/use_case/inference_runner/src/UseCaseHandler.cc",
         "source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup"),
    ]
    for a, b in pairs:
        r = sh("diff %s/%s %s/%s" % (KIT, a, KIT, b))
        ok = ok and r.returncode == 0
    if not ok:
        stop("revert verification failed")
    log("[revert] verified clean")


log("== phase A: clean builds ==")
patches("patch_app.py")
for c in cells:
    build(c, "clean", c["art"])
reverts("patch_app.py")

log("== phase B: profiled builds ==")
patches("patch_app.py", "patch_driver_u85_v2.py")
for c in cells:
    if c["instr_meta"]["profiled"] == "OK":
        build(c, "prof", c["instr"])
reverts("patch_driver_u85_v2.py", "patch_app.py")

# ---------- stage 3: runs ----------------------------------------------
CRC_RE = re.compile(r"C04_OUTPUT_CRC\[(\d+)\]: bytes=(\d+) crc32=(0x[0-9A-F]+)")
TOT_RE = re.compile(r"NPU TOTAL: (\d+) cycles")
ACT_RE = re.compile(r"NPU ACTIVE: (\d+) cycles")
IDL_RE = re.compile(r"NPU IDLE: (\d+) cycles")
CNT_RE = re.compile(r"Total number of inferences:\s*(\d+)")


def run_fvp(axf, uart, macs, timeout=300):
    for f in (uart,):
        try: os.remove(f)
        except OSError: pass
    cmd = [FVP, "-a", axf,
           "-C", "mps4_board.subsystem.ethosu.num_macs=%d" % macs,
           "-C", "mps4_board.visualisation.disable-visualisation=1",
           "-C", "mps4_board.telnetterminal0.start_telnet=0",
           "-C", "mps4_board.uart0.out_file=" + uart,
           "-C", "mps4_board.uart0.unbuffered_output=1"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    t0 = time.monotonic()
    txt = ""
    while time.monotonic() - t0 < timeout:
        try:
            txt = open(uart).read()
        except OSError:
            txt = ""
        if CNT_RE.search(txt) or "Inference failed" in txt:
            break
        time.sleep(1)
    time.sleep(3)
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        pass
    return open(uart).read() if os.path.exists(uart) else ""


def extract(txt):
    v = {}
    for name, rx in (("total", TOT_RE), ("active", ACT_RE), ("idle", IDL_RE),
                     ("count", CNT_RE)):
        m = rx.search(txt)
        v[name] = int(m.group(1)) if m else None
    v["crc"] = ";".join("%s:%s:%s" % g for g in CRC_RE.findall(txt))
    pl = [l for l in txt.replace("\x00", "").splitlines()
          if l.startswith("PLPROF")]
    v["plprof"] = "\n".join(pl)
    v["pl_count"] = None
    m = re.search(r"PLPROF_BEGIN,(\d+)", txt)
    if m:
        v["pl_count"] = int(m.group(1))
    return v


results = []
for c in cells:
    d = os.path.join(PD, c["cell"])
    for arm in ("clean", "prof"):
        if arm == "prof" and c["instr_meta"]["profiled"] != "OK":
            continue
        axf = os.path.join(d, "%s.axf" % arm)
        vecs = []
        for r in (1, 2, 3):
            done = os.path.join(d, "%s.run%d.json" % (arm, r))
            uart = os.path.join(d, "%s.run%d.uart.log" % (arm, r))
            if os.path.exists(done):
                vecs.append(json.load(open(done)))
                continue
            txt = run_fvp(axf, uart, c["macs"])
            v = extract(txt)
            if v["count"] != 1 or (arm == "clean" and v["total"] is None):
                stop("run invalid %s/%s/r%d: count=%s total=%s"
                     % (c["cell"], arm, r, v["count"], v["total"]))
            json.dump(v, open(done, "w"))
            vecs.append(v)
        keys = ("total", "active", "idle", "crc", "plprof", "pl_count")
        for k in keys:
            if not (vecs[0][k] == vecs[1][k] == vecs[2][k]):
                stop("EXACT-EQUALITY FAILURE %s/%s field=%s" % (c["cell"], arm, k))
        log("[run] %s/%s x3 exact-equal total=%s pl=%s"
            % (c["cell"], arm, vecs[0]["total"], vecs[0]["pl_count"]))
        results.append({"cell": c["cell"], "arm": arm, **vecs[0]})

# output-identity gate: clean crc == prof crc per cell
by = {}
for r in results:
    by.setdefault(r["cell"], {})[r["arm"]] = r
for cell, arms in by.items():
    if "prof" in arms and arms["clean"]["crc"] != arms["prof"]["crc"]:
        stop("OUTPUT MISMATCH clean vs prof for " + cell)
log("output identity: all profiled cells match clean")

# ---------- stage 4: matrix csv ----------------------------------------
import csv as _csv
with open(os.path.join(PD, "U85_FORMAL_MATRIX.csv"), "w", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["cell", "model", "binding", "macs", "system_config",
                "vela_sha256", "instr_status", "irq_count", "instr_sha256",
                "clean_axf_sha256", "prof_axf_sha256", "timing_adapter",
                "clean_total", "clean_active", "clean_idle",
                "prof_pl_records", "prof_tail_total", "output_crc",
                "runs_exact_equal"])
    for c in cells:
        d = os.path.join(PD, c["cell"])
        cb = json.load(open(os.path.join(d, "clean.build.json")))
        pb_p = os.path.join(d, "prof.build.json")
        pb = json.load(open(pb_p)) if os.path.exists(pb_p) else {}
        cl = by[c["cell"]]["clean"]
        pr = by[c["cell"]].get("prof")
        w.writerow([c["cell"], c["model"], c["label"], c["macs"], c["syscfg"],
                    c["vela_sha"], c["instr_meta"]["profiled"],
                    c["instr_meta"].get("irq_count"),
                    c["instr_meta"].get("instr_sha256"),
                    cb["axf_sha256"], pb.get("axf_sha256"),
                    cb["timing_adapter"],
                    cl["total"], cl["active"], cl["idle"],
                    pr["pl_count"] if pr else None,
                    pr["total"] if pr else None,
                    cl["crc"], "3/3"])
log("U85_FORMAL_MATRIX.csv written")
log("DONE_P0D")
