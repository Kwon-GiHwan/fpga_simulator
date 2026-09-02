#!/usr/bin/env python3
"""P1-A clean memory-robustness acquisition (frozen contract 1c4f634).
16 new cells: 4 workloads x 2 MAC x {Sram_Only, Shared_Sram}. T-DS cells
are reused from frozen P0. Per-cell executability failures are recorded
results; only harness-level anomalies STOP."""
import hashlib, json, os, re, signal, shutil, subprocess, sys, time

KIT = "/opt/arm/ml-embedded-evaluation-kit"
P1 = "/work/u85mech/p1"
FVP = "/opt/arm/fvp_installed_320/models/Linux64_GCC-9.3/FVP_Corstone_SSE-320"
MODELS = {
    "rnnoise_INT8": "noise_reduction/rnnoise_INT8.tflite",
    "dnn_s_quantized": "inference_runner/dnn_s_quantized.tflite",
    "vww4_128_128_INT8": "vww/vww4_128_128_INT8.tflite",
    "yolo-fastest_192_face_v4": "object_detection/yolo-fastest_192_face_v4.tflite",
}
FROZEN_SHA = {
    "rnnoise_INT8": "9c582545b7c13af44616c44b654f4fe721aa2585630b0ca173ca3589f6f11c2c",
    "dnn_s_quantized": "b34dea022996706a558f14fbc967631889cbc82b93f25d326c581763aed71f0b",
    "vww4_128_128_INT8": "5e76364e80c45776b735563679d45f611cab7ce7fef2ec4e2db088afe009ccae",
    "yolo-fastest_192_face_v4": "e94bcdb011784bead70ab0c0e9d2dae1a9ea5f103b43e1e6fac3019302cf71ab",
}
MACS = [(256, "Ethos_U85_SYS_DRAM_Low"), (512, "Ethos_U85_SYS_DRAM_Mid_512")]
MODES = ["Sram_Only", "Shared_Sram"]
FATAL = ("Failed to resize buffer", "tensor allocation failed",
         "Failed to initialise model", "Arm Ethos-U NPU initialisation failed",
         "Failed to allocate tensors", "Invoke failed.", "Inference failed.")
CNT_RE = re.compile(r"Total number of inferences:\s*(\d+)")

def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True,
                          env=dict(os.environ, SOURCE_DATE_EPOCH="1776763519"))

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def stop(m):
    print("STOP:", m, flush=True); sys.exit(2)

def log(*a): print(*a, flush=True)

os.makedirs(P1, exist_ok=True)
r = sh("python3 /tmp/patch_app.py")
if r.returncode != 0: stop("app patch: " + r.stdout + r.stderr)

results = []
for model, rel in MODELS.items():
    src = os.path.join(KIT, "resources_downloaded", rel)
    if sha256(src) != FROZEN_SHA[model]:
        stop("model sha drift " + model)
    for mode in MODES:
        for macs, syscfg in MACS:
            cell = "%s__%s__%d" % (model, mode, macs)
            d = os.path.join(P1, cell); os.makedirs(d, exist_ok=True)
            res_p = os.path.join(d, "result.json")
            if os.path.exists(res_p):
                results.append(json.load(open(res_p))); log("[skip]", cell); continue
            res = {"cell": cell, "model": model, "mode": mode, "macs": macs,
                   "system_config": syscfg, "status": None}
            vd = os.path.join(d, "vela")
            art = os.path.join(vd, "%s_vela.tflite" % model)
            if not os.path.exists(art):
                shutil.rmtree(vd, ignore_errors=True); os.makedirs(vd)
                r = sh("vela --accelerator-config ethos-u85-%d --config %s/scripts/vela/default_vela.ini "
                       "--system-config %s --memory-mode %s --optimise Performance "
                       "--output-dir %s %s" % (macs, KIT, syscfg, mode, vd, src))
                if not os.path.exists(art):
                    res["status"] = "NOT_COMPILABLE"
                    res["log_tail"] = (r.stdout + r.stderr)[-400:]
                    json.dump(res, open(res_p, "w")); results.append(res)
                    log("[cell]", cell, "NOT_COMPILABLE"); continue
            res["vela_sha256"] = sha256(art)
            bdir = os.path.join(d, "build")
            axf_keep = os.path.join(d, "clean.axf")
            if not os.path.exists(axf_keep):
                shutil.rmtree(bdir, ignore_errors=True)
                r = sh("cmake -B %s -S %s -DCMAKE_TOOLCHAIN_FILE=%s/scripts/cmake/toolchains/bare-metal-gcc.cmake "
                       "-DTARGET_PLATFORM=mps4 -DTARGET_SUBSYSTEM=sse-320 -DETHOS_U_NPU_ID=U85 "
                       "-DETHOS_U_NPU_CONFIG_ID=Z%d -DETHOS_U_NPU_MEMORY_MODE=%s "
                       "-DETHOS_U_NPU_ENABLED=ON -DUSE_CASE_BUILD=inference_runner "
                       "-Dinference_runner_ACTIVATION_BUF_SZ=0x00200000 "
                       "-Dinference_runner_MODEL_PATH=%s" % (bdir, KIT, KIT, macs, mode, art))
                if r.returncode != 0:
                    res["status"] = "NOT_CONFIGURABLE"; res["log_tail"] = (r.stdout + r.stderr)[-400:]
                    json.dump(res, open(res_p, "w")); results.append(res)
                    log("[cell]", cell, "NOT_CONFIGURABLE"); continue
                r = sh("cmake --build %s -j $(nproc)" % bdir)
                axf = os.path.join(bdir, "bin", "mlek_inference_runner.axf")
                if r.returncode != 0 or not os.path.exists(axf):
                    res["status"] = "NOT_EXECUTABLE_MEMORY(link)"
                    res["log_tail"] = (r.stdout + r.stderr)[-400:]
                    json.dump(res, open(res_p, "w")); results.append(res)
                    log("[cell]", cell, res["status"]); shutil.rmtree(bdir, ignore_errors=True); continue
                shutil.copy2(axf, axf_keep); shutil.rmtree(bdir, ignore_errors=True)
            res["axf_sha256"] = sha256(axf_keep)
            vecs = []
            bad = None
            for i in (1, 2, 3):
                uart = os.path.join(d, "run%d.uart.log" % i)
                try: os.remove(uart)
                except OSError: pass
                p = subprocess.Popen([FVP, "-a", axf_keep,
                    "-C", "mps4_board.subsystem.ethosu.num_macs=%d" % macs,
                    "-C", "mps4_board.visualisation.disable-visualisation=1",
                    "-C", "mps4_board.telnetterminal0.start_telnet=0",
                    "-C", "mps4_board.uart0.out_file=" + uart,
                    "-C", "mps4_board.uart0.unbuffered_output=1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True)
                t0 = time.monotonic(); txt = ""
                while time.monotonic() - t0 < 300:
                    try: txt = open(uart).read()
                    except OSError: txt = ""
                    if CNT_RE.search(txt) or any(f in txt for f in FATAL): break
                    time.sleep(1)
                time.sleep(3)
                try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except Exception: pass
                txt = open(uart).read() if os.path.exists(uart) else ""
                if any(f in txt for f in FATAL) or not CNT_RE.search(txt):
                    bad = "NOT_EXECUTABLE_MEMORY(runtime)" if any(
                        f in txt for f in FATAL) else "RUN_TIMEOUT"
                    break
                m = re.search(r"NPU TOTAL: (\d+)", txt)
                crc = ";".join("%s:%s:%s" % g for g in re.findall(
                    r"C04_OUTPUT_CRC\[(\d+)\]: bytes=(\d+) crc32=(0x[0-9A-F]+)", txt))
                vecs.append({"total": int(m.group(1)), "crc": crc})
            if bad == "RUN_TIMEOUT":
                stop("run timeout (harness) " + cell)
            if bad:
                res["status"] = bad
            else:
                if not (vecs[0] == vecs[1] == vecs[2]):
                    stop("EXACT-EQUALITY FAILURE " + cell)
                res["status"] = "OK"; res["total"] = vecs[0]["total"]
                res["crc"] = vecs[0]["crc"]
            json.dump(res, open(res_p, "w")); results.append(res)
            log("[cell]", cell, res["status"], res.get("total", ""))
sh("python3 /tmp/patch_app.py --revert")
r = sh("diff %s/source/app/use_case/inference_runner/src/UseCaseHandler.cc "
       "%s/source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup" % (KIT, KIT))
if r.returncode != 0: stop("revert check failed")
json.dump(results, open(os.path.join(P1, "p1a_results.json"), "w"), indent=1)
log("DONE_P1A")
