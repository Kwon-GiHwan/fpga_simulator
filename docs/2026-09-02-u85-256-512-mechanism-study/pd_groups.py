#!/usr/bin/env python3
"""P0-E group-level differential: the finest COMMON attribution partition.

Ops are merged (union-find) whenever they share an attribution unit on
EITHER side of a binding pair; every unit then lies inside exactly one
group on both sides, so group cycles are exact sums on both sides and the
group delta is exact. This is the honest decomposition floor for cells
whose small ops merge into mixed IRQ-service windows (rnnoise).
Computed from the analyzer's unit table; no new measurement."""
import csv
import os
import sys
from collections import defaultdict

PAIRS = [("B-frozen", "256_Low", "512_Mid512"),
         ("B-held", "256_Low", "512_Low")]


def find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(parent, a, b):
    ra, rb = find(parent, a), find(parent, b)
    if ra != rb:
        parent[rb] = ra


def main(root):
    units = list(csv.DictReader(open(os.path.join(root, "U85_ATTRIBUTION_UNITS.csv"))))
    diff = list(csv.DictReader(open(os.path.join(root, "U85_256_512_DIFFERENTIAL.csv"))))
    # op_type lookup by (workload, sid) from diff rows
    op_ident = {}
    for r in diff:
        op_ident[(r["workload"], r["source_id"])] = (r["op_type"], r["op_identity"])
    out = []
    workloads = sorted({u["workload"] for u in units})
    for w in workloads:
        for pair, a_lbl, b_lbl in PAIRS:
            ua = [u for u in units if u["workload"] == w and u["binding"] == a_lbl]
            ub = [u for u in units if u["workload"] == w and u["binding"] == b_lbl]
            sids = set()
            for u in ua + ub:
                sids |= set(u["source_ids"].split())
            parent = {s: s for s in sids}
            for u in ua + ub:
                ms = u["source_ids"].split()
                for m in ms[1:]:
                    union(parent, ms[0], m)
            groups = defaultdict(set)
            for s in sids:
                groups[find(parent, s)].add(s)

            def gsum(us_):
                g = defaultdict(int)
                for u in us_:
                    r = find(parent, u["source_ids"].split()[0])
                    g[r] += int(u["ccnt"])
                return g

            ga, gb = gsum(ua), gsum(ub)
            if set(ga) != set(gb):
                raise SystemExit("REJECT: group cover mismatch %s %s" % (w, pair))
            for root_id in sorted(groups, key=lambda r: -abs(gb[r] - ga[r])):
                members = sorted(groups[root_id], key=int)
                types = sorted({op_ident.get((w, m), ("SYNC", ""))[0]
                                if m != "-1" else "KERNEL_WAIT" for m in members})
                out.append({
                    "workload": w, "binding_pair": pair,
                    "group_root": root_id, "n_ops": len(members),
                    "member_source_ids": " ".join(members),
                    "member_types": " ".join(types),
                    "cycles_256": ga[root_id], "cycles_512": gb[root_id],
                    "delta": gb[root_id] - ga[root_id],
                    "direction": ("REGRESS" if gb[root_id] > ga[root_id]
                                  else "IMPROVE" if gb[root_id] < ga[root_id]
                                  else "SAME")})
    with open(os.path.join(root, "U85_GROUP_DIFFERENTIAL.csv"), "w",
              newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(out[0]))
        wtr.writeheader()
        wtr.writerows(out)
    print("group rows:", len(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
