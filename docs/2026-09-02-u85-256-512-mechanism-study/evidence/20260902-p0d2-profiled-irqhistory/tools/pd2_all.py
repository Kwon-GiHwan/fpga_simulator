#!/usr/bin/env python3
"""P0-D profiled-arm v3 re-acquisition (one-hot IRQ history attribution).
Clean arms are NOT touched (frozen P0-D evidence reused). Append-only."""
import hashlib, json, os, re, signal, shutil, subprocess, sys, time

KIT = "/opt/arm/ml-embedded-evaluation-kit"
ART = "/work/u85mech/artifacts"
PD = "/work/u85mech/pd2"
OLD = "/work/u85mech/pd"
FVP = "/opt/arm/fvp_installed_320/models/Linux64_GCC-9.3/FVP_Corstone_SSE-320"
AUDIT = json.load(open("/work/u85mech/c0_audit_report.json"))
AUDIT_SHA = {c["cell"]: c["vela_sha256"] for c in AUDIT["cells"]}
MODELS = ["rnnoise_INT8", "vww4_128_128_INT8", "yolo-fastest_192_face_v4",
          "kws_micronet_m", "ad_medium_int8"]
BINDINGS = [("256_Low", 256), ("512_Mid512", 512), ("512_Low", 512)]

def sh(cmd):
    env = dict(os.environ, SOURCE_DATE_EPOCH="1776763519")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def stop(m):
    print("STOP:", m, flush=True); sys.exit(2)

def log(*a): print(*a, flush=True)

cells = [{"cell": "%s__%s" % (m, l), "model": m, "macs": mc}
         for m in MODELS for l, mc in BINDINGS]
os.makedirs(PD, exist_ok=True)

for c in cells:
    d = os.path.join(PD, c["cell"]); os.makedirs(d, exist_ok=True)
    art = os.path.join(ART, c["cell"], "%s_vela.tflite" % c["model"])
    if sha256(art) != AUDIT_SHA[c["cell"]]:
        stop("artifact drift " + c["cell"])
    instr = os.path.join(d, "instr_oh.tflite")
    meta_p = os.path.join(d, "instr.meta.json")
    if not os.path.exists(meta_p):
        r = sh("python3 /tmp/insert_irq.py %s %s --all --onehot" % (art, instr))
        if r.returncode != 0:
            stop("insert failed %s: %s" % (c["cell"], r.stdout[-200:]))
        m = re.search(r"IRQ-ALL x(\d+)", r.stdout)
        json.dump({"irq_count": int(m.group(1)), "instr_sha256": sha256(instr),
                   "encoding": "onehot"}, open(meta_p, "w"))
    c["meta"] = json.load(open(meta_p)); c["instr"] = instr
    log("[instr]", c["cell"], "IRQs", c["meta"]["irq_count"])

log("== builds (driver v3) ==")
for p in ("patch_app.py", "patch_driver_u85_v3.py"):
    r = sh("python3 /tmp/" + p)
    if r.returncode != 0: stop("patch " + p + ": " + r.stdout + r.stderr)
for c in cells:
    d = os.path.join(PD, c["cell"])
    axf_out = os.path.join(d, "prof.axf"); meta_out = os.path.join(d, "prof.build.json")
    if os.path.exists(meta_out): continue
    b = os.path.join(d, "build")
    shutil.rmtree(b, ignore_errors=True)
    r = sh("cmake -B %s -S %s -DCMAKE_TOOLCHAIN_FILE=%s/scripts/cmake/toolchains/bare-metal-gcc.cmake "
           "-DTARGET_PLATFORM=mps4 -DTARGET_SUBSYSTEM=sse-320 -DETHOS_U_NPU_ID=U85 "
           "-DETHOS_U_NPU_CONFIG_ID=Z%d -DETHOS_U_NPU_MEMORY_MODE=Dedicated_Sram "
           "-DETHOS_U_NPU_ENABLED=ON -DUSE_CASE_BUILD=inference_runner "
           "-Dinference_runner_ACTIVATION_BUF_SZ=0x00200000 -Dinference_runner_MODEL_PATH=%s"
           % (b, KIT, KIT, c["macs"], c["instr"]))
    if r.returncode != 0: stop("cfg " + c["cell"] + r.stderr[-200:])
    r = sh("cmake --build %s -j $(nproc)" % b)
    axf = os.path.join(b, "bin", "mlek_inference_runner.axf")
    if r.returncode != 0 or not os.path.exists(axf):
        stop("build " + c["cell"] + (r.stdout + r.stderr)[-300:])
    shutil.copy2(axf, axf_out)
    json.dump({"axf_sha256": sha256(axf_out)}, open(meta_out, "w"))
    shutil.rmtree(b, ignore_errors=True)
    log("[build]", c["cell"], sha256(axf_out)[:12])
for p in ("patch_driver_u85_v3.py", "patch_app.py"):
    sh("python3 /tmp/%s --revert" % p)
for a, b in (("dependencies/core-driver/src/ethosu_driver.c", ".bak"),
             ("dependencies/core-driver/src/ethosu_device_u85.c", ".bak.v3"),
             ("source/app/use_case/inference_runner/src/UseCaseHandler.cc", ".bak.cgroup")):
    base = os.path.join(KIT, a)
    bak = base.replace(".c", ".c" + b) if b != ".bak.cgroup" else base + "" 
for pair in (("dependencies/core-driver/src/ethosu_driver.c",
              "dependencies/core-driver/src/ethosu_driver.c.bak"),
             ("dependencies/core-driver/src/ethosu_device_u85.c",
              "dependencies/core-driver/src/ethosu_device_u85.c.bak.v3"),
             ("source/app/use_case/inference_runner/src/UseCaseHandler.cc",
              "source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup")):
    r = sh("diff %s/%s %s/%s" % (KIT, pair[0], KIT, pair[1]))
    if r.returncode != 0: stop("revert check failed " + pair[0])
log("[revert] verified clean")

log("== runs ==")
CNT_RE = re.compile(r"Total number of inferences:\s*(\d+)")

def run_fvp(axf, uart, macs):
    try: os.remove(uart)
    except OSError: pass
    p = subprocess.Popen([FVP, "-a", axf,
        "-C", "mps4_board.subsystem.ethosu.num_macs=%d" % macs,
        "-C", "mps4_board.visualisation.disable-visualisation=1",
        "-C", "mps4_board.telnetterminal0.start_telnet=0",
        "-C", "mps4_board.uart0.out_file=" + uart,
        "-C", "mps4_board.uart0.unbuffered_output=1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 300:
        try: txt = open(uart).read()
        except OSError: txt = ""
        if CNT_RE.search(txt) or "Inference failed" in txt: break
        time.sleep(1)
    time.sleep(3)
    try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception: pass
    return open(uart).read() if os.path.exists(uart) else ""

def extract(txt):
    v = {}
    v["count"] = int(CNT_RE.search(txt).group(1)) if CNT_RE.search(txt) else None
    m = re.search(r"NPU TOTAL: (\d+)", txt); v["total"] = int(m.group(1)) if m else None
    v["crc"] = ";".join("%s:%s:%s" % m for m in re.findall(
        r"C04_OUTPUT_CRC\[(\d+)\]: bytes=(\d+) crc32=(0x[0-9A-F]+)", txt))
    v["plprof"] = "\n".join(l for l in txt.replace("\x00", "").splitlines()
                            if l.startswith("PLPROF"))
    m = re.search(r"PLPROF_BEGIN,(\d+)", txt)
    v["pl_count"] = int(m.group(1)) if m else None
    return v

for c in cells:
    d = os.path.join(PD, c["cell"])
    vecs = []
    for r in (1, 2, 3):
        done = os.path.join(d, "prof.run%d.json" % r)
        uart = os.path.join(d, "prof.run%d.uart.log" % r)
        if os.path.exists(done):
            vecs.append(json.load(open(done))); continue
        txt = run_fvp(os.path.join(d, "prof.axf"), uart, c["macs"])
        v = extract(txt)
        if v["count"] != 1: stop("run invalid %s r%d" % (c["cell"], r))
        json.dump(v, open(done, "w")); vecs.append(v)
    for k in ("total", "crc", "plprof", "pl_count"):
        if not (vecs[0][k] == vecs[1][k] == vecs[2][k]):
            stop("EXACT-EQUALITY FAILURE %s %s" % (c["cell"], k))
    old_clean = json.load(open(os.path.join(OLD, c["cell"], "clean.run1.json")))
    if old_clean["crc"] != vecs[0]["crc"]:
        stop("OUTPUT MISMATCH vs frozen clean " + c["cell"])
    log("[run]", c["cell"], "x3 exact-equal pl=%s crc-ok" % vecs[0]["pl_count"])
log("DONE_P0D2")
