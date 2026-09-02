#!/usr/bin/env python3
"""C0-4 runtime phase: run orig/control/irq1 AXFs on FVP_Corstone_SSE-320,
capture UART, and evaluate the C0-4 validation items."""
import os, re, signal, subprocess, sys, time

FVP = os.environ.get("C04_FVP", "/opt/arm/fvp_installed_320/models/Linux64_GCC-9.3/FVP_Corstone_SSE-320")
ROOT = sys.argv[1]           # evidence root holding the AXFs
MACS = 512
COMPLETE = "Inference completed."
COUNT_RE = re.compile(r"Total number of inferences:\s*(\d+)")
FATAL = ("Failed to resize buffer", "tensor allocation failed",
         "Failed to initialise model", "Arm Ethos-U NPU initialisation failed",
         "Failed to allocate tensors", "Invoke failed.", "Inference failed.")

def run(name):
    axf = os.path.join(ROOT, name + ".axf")
    uart = os.path.join(ROOT, name + ".uart.log")
    log = os.path.join(ROOT, name + ".fvp.log")
    for f in (uart, log):
        if os.path.exists(f): os.remove(f)
    cmd = [FVP, "-a", axf,
           "-C", "mps4_board.subsystem.ethosu.num_macs=%d" % MACS,
           "-C", "mps4_board.visualisation.disable-visualisation=1",
           "-C", "mps4_board.telnetterminal0.start_telnet=0",
           "-C", "mps4_board.uart0.out_file=" + uart,
           "-C", "mps4_board.uart0.unbuffered_output=1"]
    p = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0 = time.monotonic(); status = None
    while time.monotonic() - t0 < 900:
        try: txt = open(uart).read()
        except OSError: txt = ""
        if any(f in txt for f in FATAL):
            status = "FATAL"; break
        m = COUNT_RE.search(txt)
        if m:
            time.sleep(3)          # let trailing prints flush
            status = "COMPLETE(count=%s)" % m.group(1); break
        if p.poll() is not None:
            status = "FVP_EXITED_EARLY"; break
        time.sleep(1)
    else:
        status = "TIMEOUT"
    try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception: pass
    txt = open(uart).read() if os.path.exists(uart) else ""
    layers = re.search(r"PER-LAYER NPU PROFILING \((\d+) layers\)", txt)
    print("%-8s %s  wall=%.0fs  prof_layers=%s" %
          (name, status, time.monotonic() - t0,
           layers.group(1) if layers else "no-print"))
    return txt

def dump_block(txt):
    i = txt.find("output tensors post inference")
    j = txt.find("Total number of inferences")
    return txt[i:j] if i >= 0 and j > i else None

t = {n: run(n) for n in ("orig", "control", "irq1")}
d = {n: dump_block(t[n]) for n in t}
print("output dump present:", {n: d[n] is not None for n in d})
print("orig==control:", d["orig"] == d["control"])
print("orig==irq1  :", d["orig"] == d["irq1"])
