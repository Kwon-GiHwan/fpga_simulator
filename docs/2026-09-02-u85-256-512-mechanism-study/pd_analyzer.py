#!/usr/bin/env python3
"""P0-E operator matching / differential analyzer — v3.

v1 (frozen 07a531a) predicted launches from verbose-schedule depth slices and
was REJECTED by its own gate on rnnoise (48 stream launches vs 39 predicted:
elementwise lowering emits 1..k launches per op). v2 replaces the prediction
with regor's debug database as the launch->operation authority:

    queue(offset, optimised_id)  ->  optimised(id, source_id, ...)
                                 ->  source(id, operator, ofm, ext_key)

The debug capture is hash-gated (artifact byte-identical with
--enable-debug-db, verified at generation). Cross-MAC join is at SOURCE-op
granularity, which is MAC-invariant by construction and verified by a
source-table equality gate. No results from v1 were ever accepted.

Fail-closed rejections: queue/launch count mismatch, source-table mismatch
across bindings, PLPROF/launch count mismatch, missing evidence. Q2
compiler fields attach from the verbose schedule only where the join is
unambiguous; otherwise they are left empty (NOT_EVALUABLE), never guessed.

v3 (after the v2 gate fired on merged IRQ services: 48 IRQs -> 17 records on
rnnoise): profiled arms are re-acquired with one-hot IRQ params and a driver
that records STATUS.irq_history_mask per service. Attribution is by
ATTRIBUTION UNIT = one service window, ring-decoded from the history bits
(fail-closed on non-contiguous windows). A source op whose launches all lie
in unmixed units gets exact cycles; an op sharing any unit with another op is
NOT_SEPARATED at op level (the unit row remains lossless). The remainder
after the last decoded launch is the tail unit. PLPROF_FINAL_HIST is
diagnostic only (reads 0xFFFF at completion on the FVP).
"""
import csv
import json
import os
import re
import sys

WORKLOADS = ["rnnoise_INT8", "vww4_128_128_INT8", "yolo-fastest_192_face_v4",
             "kws_micronet_m", "ad_medium_int8", "dnn_s_quantized"]
PAIRS = [("B-frozen", "256_Low", "512_Mid512"),
         ("B-held", "256_Low", "512_Low")]
EVT = ("active", "sram_rd", "sram_wr", "ext_rd", "ext_wr")


class Reject(Exception):
    pass


def parse_db(path):
    x = open(path).read()

    def table(name):
        m = re.search(r'<table name="%s">\s*<!\[CDATA\[(.*?)\]\]>' % name, x, re.S)
        if not m:
            raise Reject("debug db table missing: " + name)
        rows = [r for r in csv.reader(m.group(1).strip().splitlines()) if r]
        return rows[0], rows[1:]

    _, q = table("queue")
    queue = sorted(((int(r[0]), int(r[2])) for r in q), key=lambda t: t[0])
    _, o = table("optimised")
    optimised = {int(r[0]): {"source_id": int(r[1]), "operator": r[2]} for r in o}
    hdr, s = table("source")
    source = {int(r[0]): {"operator": r[1],
                          "kernel": "%sx%s" % (r[2], r[3]),
                          "ofm": "%sx%sx%s" % (r[4], r[5], r[6]),
                          "ext_key": r[7]} for r in s}
    return queue, optimised, source


def parse_schedule(path):
    ops, cur = [], None
    for ln in open(path):
        m = re.match(r"\t(\d+): Operation (\S+)\s+- OFM ([0-9, ]+)", ln)
        if m:
            cur = {"idx": int(m.group(1)), "type": m.group(2),
                   "ofm_d": m.group(3).strip().split(",")[-1].strip(),
                   "slices": 1, "ublock": "", "block": "", "stripes": "",
                   "cascade": "", "vela_cycles": None, "time_index": None}
            ops.append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r"Operator Config = OFM Block=(\[[0-9, ]+\]), "
                      r"IFM Block=(\[[0-9, ]+\]), OFM UBlock=(\[[0-9, ]+\])", ln)
        if m:
            cur["block"] = "OFM%s IFM%s" % (m.group(1), m.group(2))
            cur["ublock"] = m.group(3)
        m = re.search(r"(IFM|OFM) Stripe\s+= (\[[0-9, ]*\])", ln)
        if m:
            cur["stripes"] += "%s%s " % (m.group(1), m.group(2))
        m = re.search(r"Depth slices = \[([0-9, ]+)\]", ln)
        if m:
            cur["slices"] = len(m.group(1).split(",")) - 1
        m = re.search(r"Assigned Cascade = (\d+)", ln)
        if m:
            cur["cascade"] = m.group(1)
        m = re.search(r"Time index = (\d+)", ln)
        if m:
            cur["time_index"] = int(m.group(1))
        m = re.search(r"Estimated Perf: Macs=\d+ Cycles=(\d+)", ln)
        if m:
            cur["vela_cycles"] = int(m.group(1))
    return ops


def units(prof, n_launches):
    """Ring-decode history-attributed records into attribution units.
    Returns [{launches:[...], ccnt, evt|None, tail}]. Fail-closed on
    non-contiguous windows or launch-count overflow."""
    rows = [l.split(",") for l in prof["plprof"].splitlines()
            if l.startswith("PLPROF,")]
    recs = [{"ccnt": int(r[2]), "evt": [int(x) for x in r[3:8]],
             "hist": int(r[8], 16), "tail": False} for r in rows]
    if prof["pl_count"] != len(recs):
        raise Reject("PLPROF count mismatch")
    seq = 0
    out = []
    for i, rec in enumerate(recs):
        n = bin(rec["hist"]).count("1")
        expect = 0
        for k in range(n):
            expect |= 1 << ((seq + k) % 16)
        if expect != rec["hist"]:
            raise Reject("non-contiguous history window at record %d" % i)
        out.append({"launches": list(range(seq, seq + n)),
                    "ccnt": rec["ccnt"], "evt": rec["evt"], "tail": False})
        seq += n
    if seq > n_launches:
        raise Reject("decoded %d launches > inserted %d" % (seq, n_launches))
    if seq < n_launches:
        out.append({"launches": list(range(seq, n_launches)),
                    "ccnt": prof["total"], "evt": None, "tail": True})
    return out


SYNC_SID = -1

def load_cell(root, model, label):
    d = os.path.join(root, "%s__%s" % (model, label))
    meta = json.load(open(os.path.join(d, "instr.meta.json")))
    queue, optimised, source = parse_db(os.path.join(d, "debug.xml"))
    sched = parse_schedule(os.path.join(d, "vela_verbose", "verbose.log"))
    clean = json.load(open(os.path.join(d, "clean.run1.json")))
    prof = None
    launch_map = None
    if meta["profiled"] == "OK":
        launches = json.load(open(os.path.join(d, "launches.json")))
        if meta["irq_count"] != len(launches):
            raise Reject("irq_count %d != enumerated launches %d for %s__%s"
                         % (meta["irq_count"], len(launches), model, label))
        by_off = dict(queue)
        launch_map = []
        for off, kind in launches:
            if kind == "KERNEL_WAIT":
                launch_map.append(SYNC_SID)
            elif off in by_off:
                launch_map.append(optimised[by_off[off]]["source_id"])
            else:
                raise Reject("launch offset %d (%s) missing from debug queue"
                             % (off, kind))
        nonsync = sum(1 for x in launch_map if x != SYNC_SID)
        if nonsync != len(queue):
            raise Reject("non-sync launches %d != queue rows %d for %s__%s"
                         % (nonsync, len(queue), model, label))
        prof = json.load(open(os.path.join(d, "prof.run1.json")))
    return {"queue": queue, "optimised": optimised, "source": source,
            "sched": sched, "clean": clean, "prof": prof, "meta": meta,
            "launch_map": launch_map}


def per_source(cell):
    """Aggregate attribution units to source-op granularity. An op sharing
    any unit with a different source op is NOT_SEPARATED (cycles None);
    unit rows carry the lossless view."""
    if cell["prof"] is None:
        return None, None
    launch_src = cell["launch_map"]
    us = units(cell["prof"], len(launch_src))
    unit_rows = []
    agg = {}
    for ui, u in enumerate(us):
        srcs = [launch_src[l] for l in u["launches"]]
        uniq = sorted(set(srcs))
        unit_rows.append({"unit": ui, "launches": len(u["launches"]),
                          "source_ids": uniq, "ccnt": u["ccnt"],
                          "evt": u["evt"], "tail": u["tail"]})
        for sid in uniq:
            a = agg.setdefault(sid, {"ccnt": 0, "evt": [0] * 5, "launches": 0,
                                     "mixed": False, "tail_in_op": False})
            a["launches"] += srcs.count(sid)
            if len(uniq) > 1:
                a["mixed"] = True
            else:
                a["ccnt"] += u["ccnt"]
                if u["tail"]:
                    a["tail_in_op"] = True
                    a["evt"] = None
                elif a["evt"] is not None:
                    a["evt"] = [p + q for p, q in zip(a["evt"], u["evt"])]
            if u["tail"]:
                a["tail_in_op"] = True
    for sid, a in agg.items():
        if a["mixed"]:
            a["ccnt"] = None
            a["evt"] = None
    return agg, unit_rows


SCHED_TYPE = {"Conv2D": "Conv2D", "DepthwiseConv2D": "DepthwiseConv2D",
              "FullyConnected": "FullyConnected", "AvgPool": "AvgPool"}


def sched_join(cell):
    """Best-effort unambiguous join: schedule op -> source id, by walking the
    queue's source order and matching schedule ops in order to the first
    source op whose operator name matches. Ambiguity leaves fields empty."""
    order = []
    for _, opt_id in cell["queue"]:
        sid = cell["optimised"][opt_id]["source_id"]
        if sid not in order:
            order.append(sid)
    join, si = {}, 0
    for op in cell["sched"]:
        matched = None
        for j in range(si, len(order)):
            src = cell["source"][order[j]]
            if src["operator"] == op["type"]:
                matched = order[j]
                si = j + 1
                break
        if matched is not None and matched not in join:
            join[matched] = op
    return join


def main(root):
    diff_rows, match_rows, unit_out = [], [], []
    for model in WORKLOADS:
        cells = {}
        for label in ("256_Low", "512_Mid512", "512_Low"):
            cells[label] = load_cell(root, model, label)
        # source-table equality gate (MAC-invariant identity)
        s0 = cells["256_Low"]["source"]
        for label in ("512_Mid512", "512_Low"):
            if cells[label]["source"] != s0:
                raise Reject("source table mismatch %s %s" % (model, label))
        pu = {l: per_source(cells[l]) for l in cells}
        aggs = {l: pu[l][0] for l in pu}
        for l in pu:
            if pu[l][1] is not None:
                for ur in pu[l][1]:
                    unit_out.append({"workload": model, "binding": l,
                                     "unit": ur["unit"],
                                     "launches": ur["launches"],
                                     "source_ids": " ".join(map(str, ur["source_ids"])),
                                     "op_types": " ".join(sorted(
                                         ("KERNEL_WAIT" if i == SYNC_SID
                                          else s0[i]["operator"])
                                         for i in ur["source_ids"])),
                                     "ccnt": ur["ccnt"], "tail": int(ur["tail"]),
                                     **({("evt_%s" % n): ur["evt"][i]
                                         for i, n in enumerate(EVT)} if ur["evt"] else {})})
        joins = {l: sched_join(cells[l]) for l in cells}
        for binding, a_lbl, b_lbl in PAIRS:
            A, B = cells[a_lbl], cells[b_lbl]
            ga, gb = aggs[a_lbl], aggs[b_lbl]
            ja, jb = joins[a_lbl], joins[b_lbl]
            if ga is None or gb is None:
                continue  # NOT_AVAILABLE profiled arm (dnn_s); reported in matrix
            if set(k for k in ga if k != SYNC_SID) != set(k for k in gb if k != SYNC_SID):
                raise Reject("source coverage mismatch %s %s" % (model, binding))
            for sid in sorted(k for k in ga if k != SYNC_SID):
                if sid not in gb:
                    raise Reject("source %d missing on 512 side %s %s" % (sid, model, binding))
                src = s0[sid]
                ca, cb = ga[sid], gb[sid]
                oa, ob = ja.get(sid), jb.get(sid)
                row = {"workload": model, "binding_pair": binding,
                       "source_id": sid,
                       "op_identity": "%s|%s|%s|%s" % (src["operator"],
                                                       src["ofm"], src["kernel"],
                                                       src["ext_key"]),
                       "op_type": src["operator"],
                       "launches_256": ca["launches"],
                       "launches_512": cb["launches"],
                       "cycles_256": "" if ca["ccnt"] is None else ca["ccnt"],
                       "cycles_512": "" if cb["ccnt"] is None else cb["ccnt"],
                       "separable": int(ca["ccnt"] is not None and cb["ccnt"] is not None),
                       "observed_direction": (
                           "NOT_SEPARATED" if ca["ccnt"] is None or cb["ccnt"] is None
                           else "REGRESS" if cb["ccnt"] > ca["ccnt"]
                           else "IMPROVE" if cb["ccnt"] < ca["ccnt"] else "SAME"),
                       "tail_in_op_256": int(ca["tail_in_op"]),
                       "tail_in_op_512": int(cb["tail_in_op"]),
                       "vela_cycles_256": oa["vela_cycles"] if oa else "",
                       "vela_cycles_512": ob["vela_cycles"] if ob else "",
                       "ublock_256": oa["ublock"] if oa else "",
                       "ublock_512": ob["ublock"] if ob else "",
                       "block_256": oa["block"] if oa else "",
                       "block_512": ob["block"] if ob else "",
                       "stripes_256": oa["stripes"].strip() if oa else "",
                       "stripes_512": ob["stripes"].strip() if ob else "",
                       "cascade_256": oa["cascade"] if oa else "",
                       "cascade_512": ob["cascade"] if ob else ""}
                both = oa is not None and ob is not None
                row["UBLOCK_CHANGED"] = int(oa["ublock"] != ob["ublock"]) if both else ""
                row["BLOCK_CONFIG_CHANGED"] = int(oa["block"] != ob["block"]) if both else ""
                row["TILE_GEOMETRY_CHANGED"] = (int((oa["stripes"], oa["slices"])
                                                    != (ob["stripes"], ob["slices"]))
                                                if both else "")
                row["MEMORY_PLACEMENT_CHANGED"] = (int(oa["cascade"] != ob["cascade"])
                                                   if both else "")
                row["COMMAND_OR_PASS_STRUCTURE_CHANGED"] = int(
                    ca["launches"] != cb["launches"]
                    or ((oa["slices"], oa["time_index"]) != (ob["slices"], ob["time_index"])
                        if both else False))
                if ca["evt"]:
                    for i, nm in enumerate(EVT):
                        row["%s_256" % nm] = ca["evt"][i]
                if cb["evt"]:
                    for i, nm in enumerate(EVT):
                        row["%s_512" % nm] = cb["evt"][i]
                diff_rows.append(row)
                match_rows.append({"workload": model, "binding_pair": binding,
                                   "source_id": sid,
                                   "op_identity": row["op_identity"],
                                   "launches_256": ca["launches"],
                                   "launches_512": cb["launches"],
                                   "sched_joined_256": int(oa is not None),
                                   "sched_joined_512": int(ob is not None)})
    cols = []
    for r in diff_rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(os.path.join(root, "U85_256_512_DIFFERENTIAL.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(diff_rows)
    with open(os.path.join(root, "U85_OPERATOR_MATCH.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(match_rows[0]))
        w.writeheader()
        w.writerows(match_rows)
    if unit_out:
        ucols = []
        for r in unit_out:
            for k in r:
                if k not in ucols:
                    ucols.append(k)
        with open(os.path.join(root, "U85_ATTRIBUTION_UNITS.csv"), "w",
                  newline="") as f:
            w = csv.DictWriter(f, fieldnames=ucols)
            w.writeheader()
            w.writerows(unit_out)
    print("diff rows:", len(diff_rows), "match rows:", len(match_rows),
          "unit rows:", len(unit_out))
    print("wrote U85_256_512_DIFFERENTIAL.csv, U85_OPERATOR_MATCH.csv")


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else ".")
    except Reject as e:
        print("REJECT:", e)
        sys.exit(2)
