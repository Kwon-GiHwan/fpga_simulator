"""Formal FVP Stage 3 — repetition #3, closing M1 == M2 == M3.

Same frozen anchor, same canonical order, same gates, same 19 equality-bearing
fields. M3 must equal BOTH prior repetitions. A mismatch is DETERMINISM_FAILURE:
no 2/3 majority, no M3 retry, no median, no average, no tie-break from the
qualification value.
"""
import json, os, re, shutil, signal, subprocess, sys, time

sys.path.insert(0, "/tmp/xqbin")
import ccident

KIT = "/opt/arm/ml-embedded-evaluation-kit"
ROOT = "/tmp/xq"
ARENA = 0x00200000
EPOCH = 1776763519
EXPECTED_DATE, EXPECTED_TIME = "Apr 21 2026", "09:25:19"
FREE_GATE = 1 << 30
RUN_TIMEOUT_S = 3600

COMPLETE = "Inference completed."
COUNT_RE = re.compile(r"Total number of inferences:\s*(\d+)")
FATAL = ("Failed to resize buffer", "tensor allocation failed",
         "Failed to initialise model", "Arm Ethos-U NPU initialisation failed",
         "Failed to allocate tensors")
MODEL_SRC = {
 "ad_medium_int8": "ad/ad_medium_int8.tflite",
 "kws_micronet_m": "kws/kws_micronet_m.tflite",
 "mobilenet_v2_1.0_224_INT8": "img_class/mobilenet_v2_1.0_224_INT8.tflite",
 "rnnoise_INT8": "noise_reduction/rnnoise_INT8.tflite",
 "vww4_128_128_INT8": "vww/vww4_128_128_INT8.tflite",
 "wav2letter_pruned_int8": "asr/wav2letter_pruned_int8.tflite",
 "yolo-fastest_192_face_v4": "object_detection/yolo-fastest_192_face_v4.tflite",
}
NPU_ID = {"ethos-u55": "U55", "ethos-u65": "U65", "ethos-u85": "U85"}
CFG = {"ethos-u55": "H", "ethos-u65": "Y", "ethos-u85": "Z"}
SYSCFG = {("ethos-u55", 0): "Ethos_U55_High_End_Embedded"}


def env():
    e = dict(os.environ); e["SOURCE_DATE_EPOCH"] = str(EPOCH); return e


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env())


def sha256(p):
    return sh("sha256sum %s" % p).stdout.split()[0] if os.path.exists(p) else None


def free_bytes():
    st = os.statvfs("/"); return st.f_bavail * st.f_frsize


def live_fvps():
    out = sh("ps -eo pid=,comm=,args=").stdout
    return [l.split()[0] for l in out.splitlines()
            if "FVP_Corstone" in l and "defunct" not in l]


def board_and_param(cell):
    if cell["target_platform"] == "mps4":
        return "mps4_board", "mps4_board.subsystem.ethosu.num_macs"
    return "mps3_board", "ethosu.num_macs"


def build(cell, a):
    """Rebuild at the anchored canonical path under the pinned epoch."""
    ws = os.path.join(ROOT, cell["cell_id"])
    shutil.rmtree(ws, ignore_errors=True)
    vdir = os.path.join(ws, "vela"); os.makedirs(vdir, exist_ok=True)
    src = os.path.join(KIT, "resources_downloaded", MODEL_SRC[cell["model"]])
    sh("vela --accelerator-config %s --config %s/scripts/vela/default_vela.ini "
       "--system-config %s --memory-mode %s --optimise Performance --output-dir %s %s"
       % (cell["accelerator_config"], KIT, cell["system_config"], cell["memory_mode"], vdir, src))
    art = os.path.join(vdir, "%s_vela.tflite" % cell["model"])
    if not os.path.exists(art):
        return {"ok": False, "stage": "vela", "ws": ws}
    bdir = os.path.join(ws, "build-a1")
    rc = sh("cmake -B %s -S %s "
            "-DCMAKE_TOOLCHAIN_FILE=%s/scripts/cmake/toolchains/bare-metal-gcc.cmake "
            "-DTARGET_PLATFORM=%s -DTARGET_SUBSYSTEM=%s -DETHOS_U_NPU_ID=%s "
            "-DETHOS_U_NPU_CONFIG_ID=%s -DETHOS_U_NPU_MEMORY_MODE=%s -DETHOS_U_NPU_ENABLED=ON "
            "-DUSE_CASE_BUILD=inference_runner -Dinference_runner_ACTIVATION_BUF_SZ=0x%08X "
            "-Dinference_runner_MODEL_PATH=%s"
            % (bdir, KIT, KIT, cell["target_platform"], cell["target_subsystem"],
               NPU_ID[cell["npu"]], CFG[cell["npu"]] + str(cell["mac_config"]),
               cell["memory_mode"], ARENA, art))
    if rc.returncode != 0:
        return {"ok": False, "stage": "configure", "ws": ws, "log": (rc.stdout + rc.stderr)[-1200:]}
    rb = sh("cmake --build %s -j $(nproc)" % bdir)
    axf = os.path.join(bdir, "bin", "mlek_inference_runner.axf")
    if rb.returncode != 0 or not os.path.exists(axf):
        return {"ok": False, "stage": "build", "ws": ws, "log": (rb.stdout + rb.stderr)[-1200:]}
    gen = sh("ls %s/generated/inference_runner/src/*_vela.tflite.cc" % bdir).stdout.strip().splitlines()
    gen = gen[0] if gen else None
    try:
        body = ccident.body_sha256(open(gen, "rb").read()) if gen else None
    except ccident.CanonicalizationError as e:
        return {"ok": False, "stage": "canonicalize", "ws": ws, "log": str(e)}
    ta = sh("grep -E '^ETHOS_U_NPU_TIMING_ADAPTER_ENABLED' %s/CMakeCache.txt" % bdir).stdout.strip()
    stamp = sh("arm-none-eabi-strings %s | grep -m1 'Build date:'" % axf).stdout.strip()
    return {"ok": True, "ws": ws, "axf": axf, "axf_sha256": sha256(axf),
            "vela_sha256": sha256(art), "cc_raw_sha256": sha256(gen),
            "cc_body_sha256": body, "timing_adapter_cache": ta,
            "embedded_build_stamp": stamp}


def gate(cell, b):
    """Reproduction gate. Any failure halts the whole stage."""
    checks = {
        "vela_sha_matches_anchor": b["vela_sha256"] == cell["formal_vela_sha256"],
        "cc_body_sha_matches_anchor": b["cc_body_sha256"] == cell["FORMAL_GENERATED_CC_BODY_SHA256"],
        "axf_sha_matches_anchor": b["axf_sha256"] == cell["FORMAL_REFERENCE_AXF_SHA256"],
        "timing_adapter_on": "BOOL=ON" in b["timing_adapter_cache"],
        "embedded_stamp_matches_epoch": (EXPECTED_DATE in b["embedded_build_stamp"]
                                         and EXPECTED_TIME in b["embedded_build_stamp"]),
    }
    return checks, [k for k, v in checks.items() if not v]


def run_once(cell, axf, uart, log):
    board, mac_param = board_and_param(cell)
    for f in (uart, log):
        try: os.remove(f)
        except OSError: pass
    cmd = [cell["fvp"], "-a", axf,
           "-C", "%s=%d" % (mac_param, cell["mac_config"]),
           "-C", "%s.visualisation.disable-visualisation=1" % board,
           "-C", "%s.telnetterminal0.start_telnet=0" % board,
           "-C", "%s.uart0.out_file=%s" % (board, uart),
           "-C", "%s.uart0.unbuffered_output=1" % board]
    def _read():
        try: return open(uart).read()
        except OSError: return ""
    before = set(live_fvps())
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    pgid = os.getpgid(p.pid)
    status, count = None, None
    while True:
        txt = _read()
        if any(f in txt for f in FATAL):
            status = "FAILURE_FATAL_BEFORE_COMPLETION"; break
        if COMPLETE in txt:
            m = COUNT_RE.search(txt); count = int(m.group(1)) if m else None
            status = "SUCCESS" if count == 1 else "FAILURE_COUNT_MISMATCH"; break
        if p.poll() is not None:
            time.sleep(0.3); txt = _read()
            if COMPLETE in txt:
                m = COUNT_RE.search(txt); count = int(m.group(1)) if m else None
                status = "SUCCESS" if count == 1 else "FAILURE_COUNT_MISMATCH"
            elif any(f in txt for f in FATAL):
                status = "FAILURE_FATAL_BEFORE_COMPLETION"
            else:
                status = "FAILURE_PROCESS_DIED_BEFORE_COMPLETION"
            break
        if time.monotonic() - t0 > RUN_TIMEOUT_S:
            status = "FAILURE_TIMEOUT"; break
        time.sleep(0.05)
    elapsed = time.monotonic() - t0
    try: os.killpg(pgid, signal.SIGKILL)
    except Exception: pass
    time.sleep(1.0)
    survivors = [x for x in live_fvps() if x not in before]
    txt = _read()
    def g(pat):
        m = re.search(pat, txt); return int(m.group(1)) if m else None
    return {"status": status, "inference_count_line": count,
            "wall_clock_s": round(elapsed, 3), "owned_pgid": pgid,
            "survivors_after_cleanup": survivors,
            "npu_total_cycles": g(r"NPU TOTAL:\s*(\d+)"),
            "npu_active_cycles": g(r"NPU ACTIVE:\s*(\d+)"),
            "npu_idle_cycles": g(r"NPU IDLE:\s*(\d+)"),
            "axi0_rd_beats": g(r"AXI0_RD_DATA_BEAT_RECEIVED:\s*(\d+)"),
            "axi0_wr_beats": g(r"AXI0_WR_DATA_BEAT_WRITTEN:\s*(\d+)"),
            "axi1_rd_beats": g(r"AXI1_RD_DATA_BEAT_RECEIVED:\s*(\d+)"),
            "uart_tail": txt[-2000:]}


EQUALITY_MEASUREMENT_FIELDS = (
    "status", "inference_count_line", "npu_total_cycles", "npu_active_cycles",
    "npu_idle_cycles", "axi0_rd_beats", "axi0_wr_beats", "axi1_rd_beats")
EQUALITY_ARTIFACT_FIELDS = (
    "model_sha256", "vela_sha256", "generated_cc_body_sha256", "axf_sha256")
EQUALITY_CONFIG_FIELDS = (
    "platform", "npu", "mac_config", "fvp", "timing_adapter_cache",
    "embedded_build_stamp", "source_date_epoch")


def determinism_diff(prior, key, cur_meas, cur_art, cur_cfg):
    """Exact equality against one prior repetition. Telemetry excluded."""
    bad = {}
    for k in EQUALITY_MEASUREMENT_FIELDS:
        if prior[key].get(k) != cur_meas.get(k):
            bad["measurement." + k] = [prior[key].get(k), cur_meas.get(k)]
    for k in EQUALITY_ARTIFACT_FIELDS:
        if prior["artifact_identity"].get(k) != cur_art.get(k):
            bad["artifact_identity." + k] = [prior["artifact_identity"].get(k), cur_art.get(k)]
    for k in EQUALITY_CONFIG_FIELDS:
        if prior["config_identity"].get(k) != cur_cfg.get(k):
            bad["config_identity." + k] = [prior["config_identity"].get(k), cur_cfg.get(k)]
    return bad


def stop(outdir, payload):
    json.dump(payload, open(os.path.join(outdir, "_STAGE3_STOP.json"), "w"), indent=1)
    print("STAGE3_STOP %s" % json.dumps({k: payload[k] for k in ("seq", "cell_id", "reason")}),
          flush=True)


def main():
    anchor = json.load(open(sys.argv[1]))
    outdir = sys.argv[2]
    f1 = json.load(open(sys.argv[3]))
    f2 = json.load(open(sys.argv[4]))
    m1_by_seq = {r["seq"]: r for r in f1["records"]}
    m2_by_seq = {r["seq"]: r for r in f2["records"]}
    cells = anchor["canonical_order"]
    os.makedirs(outdir, exist_ok=True)
    for cell in cells:
        dest = os.path.join(outdir, "%03d_%s.json" % (cell["seq"], cell["cell_id"]))
        if os.path.exists(dest):
            continue
        if free_bytes() < FREE_GATE:
            stop(outdir, {"seq": cell["seq"], "cell_id": cell["cell_id"],
                          "reason": "FREE_SPACE_GATE"}); return 2
        t0 = time.monotonic()
        b = build(cell, anchor)
        if not b.get("ok"):
            shutil.rmtree(b.get("ws", "/nonexistent"), ignore_errors=True)
            stop(outdir, {"seq": cell["seq"], "cell_id": cell["cell_id"],
                          "reason": "REPRODUCIBILITY_INFRASTRUCTURE_FAILURE:%s" % b.get("stage"),
                          "detail": b.get("log", "")}); return 3
        checks, bad = gate(cell, b)
        if bad:
            shutil.rmtree(b["ws"], ignore_errors=True)
            stop(outdir, {"seq": cell["seq"], "cell_id": cell["cell_id"],
                          "reason": "ARTIFACT_REPRODUCTION_MISMATCH", "failed": bad,
                          "observed": {k: b[k] for k in ("vela_sha256", "cc_body_sha256",
                                                          "axf_sha256", "timing_adapter_cache",
                                                          "embedded_build_stamp")},
                          "expected": {"vela": cell["formal_vela_sha256"],
                                       "cc_body": cell["FORMAL_GENERATED_CC_BODY_SHA256"],
                                       "axf": cell["FORMAL_REFERENCE_AXF_SHA256"]}}); return 3
        r = run_once(cell, b["axf"], os.path.join(b["ws"], "uart_m3.txt"),
                     os.path.join(b["ws"], "fvp_m3.log"))
        shutil.rmtree(b["ws"], ignore_errors=True)
        if r["status"] != "SUCCESS" or r["survivors_after_cleanup"]:
            stop(outdir, {"seq": cell["seq"], "cell_id": cell["cell_id"],
                          "reason": "HARD_STOP:%s" % r["status"],
                          "survivors": r["survivors_after_cleanup"],
                          "uart_tail": r["uart_tail"]}); return 4
        rec = {"seq": cell["seq"], "cell_id": cell["cell_id"], "repetition": 3,
               "formal_sample": "M3",
               "gate": checks,
               "artifact_identity": {
                   "model_sha256": cell["model_sha256"],
                   "vela_sha256": b["vela_sha256"],
                   "generated_cc_body_sha256": b["cc_body_sha256"],
                   "generated_cc_raw_sha256_informational": b["cc_raw_sha256"],
                   "axf_sha256": b["axf_sha256"]},
               "platform": cell["platform"], "npu": cell["npu"],
               "mac_config": cell["mac_config"], "fvp": cell["fvp"],
               "timing_adapter_cache": b["timing_adapter_cache"],
               "embedded_build_stamp": b["embedded_build_stamp"],
               "source_date_epoch": EPOCH,
               "measurement": {k: r[k] for k in
                               ("status", "inference_count_line", "npu_total_cycles",
                                "npu_active_cycles", "npu_idle_cycles", "axi0_rd_beats",
                                "axi0_wr_beats", "axi1_rd_beats", "wall_clock_s",
                                "owned_pgid", "survivors_after_cleanup")},
               "elapsed_s": round(time.monotonic() - t0, 1)}
        cur_cfg = {"platform": cell["platform"], "npu": cell["npu"],
                   "mac_config": cell["mac_config"], "fvp": cell["fvp"],
                   "timing_adapter_cache": b["timing_adapter_cache"],
                   "embedded_build_stamp": b["embedded_build_stamp"],
                   "source_date_epoch": EPOCH}
        d1 = determinism_diff(m1_by_seq[cell["seq"]], "M1", rec["measurement"],
                              rec["artifact_identity"], cur_cfg)
        d2 = determinism_diff(m2_by_seq[cell["seq"]], "M2", rec["measurement"],
                              rec["artifact_identity"], cur_cfg)
        rec["determinism"] = {"M3_equals_M1": not d1, "M3_equals_M2": not d2,
                              "M1_equals_M2_equals_M3": not (d1 or d2),
                              "mismatched_vs_M1": d1, "mismatched_vs_M2": d2}
        if d1 or d2:
            stop(outdir, {"seq": cell["seq"], "cell_id": cell["cell_id"],
                          "reason": "DETERMINISM_FAILURE",
                          "mismatched_vs_M1": d1, "mismatched_vs_M2": d2})
            return 5
        json.dump(rec, open(dest, "w"), indent=1)
        print("[%2d/74] %-48s M3 total=%-10s M1==M2==M3 wall=%6.2fs %4.0fs" %
              (cell["seq"], cell["cell_id"][:48], r["npu_total_cycles"],
               r["wall_clock_s"], rec["elapsed_s"]), flush=True)
    print("STAGE3_COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
