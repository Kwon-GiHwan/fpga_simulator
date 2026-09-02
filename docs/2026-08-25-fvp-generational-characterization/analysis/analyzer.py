"""Preregistered analysis of the frozen formal FVP evidence.

Every prohibition in ANALYSIS_PLAN.md is enforced as a rejection, not a
convention. Rules are fixed before the analyzer reads a cycle value.
"""
import csv, json, math

INCREMENTAL_STRONG = 0.75
INCREMENTAL_SATURATION = 0.50          # frozen; changing it is a rejection
CANONICAL_METRIC = "npu_total_cycles"

LADDERS = {
    ("SSE-300", "ethos-u55"): [32, 64, 128, 256],
    ("SSE-300", "ethos-u65"): [256, 512],
    ("SSE-320", "ethos-u85"): [128, 256, 512, 1024, 2048],
}
PRIMARY_PLATFORMS = {"SSE-300", "SSE-320"}
COMMON_SEMANTICS_PMU = {"CYCLE", "NPU_IDLE", "CC_STALLED_ON_BLOCKDEP"}
EQUALITY_FIELDS = ("status", "inference_count_line", "npu_total_cycles",
                   "npu_active_cycles", "npu_idle_cycles",
                   "axi0_rd_beats", "axi0_wr_beats", "axi1_rd_beats")


class AnalysisRejection(Exception):
    """A preregistered rule was violated. Never downgraded to a warning."""


def canonical_value(rec):
    """M1 is representative only after M1 == M2 == M3. Never averaged."""
    m1, m2, m3 = rec["M1"], rec["M2"], rec["M3"]
    for k in EQUALITY_FIELDS:
        if not (m1.get(k) == m2.get(k) == m3.get(k)):
            raise AnalysisRejection(
                "M1/M2/M3 disagree on %s for %s" % (k, rec["cell_id"]))
    return m1[CANONICAL_METRIC]


def assert_primary(cell):
    if cell.get("timing_adapter") == "OFF" or cell["platform"] not in PRIMARY_PLATFORMS:
        raise AnalysisRejection(
            "TA-OFF / non-primary cell %s admitted to primary analysis" % cell["cell_id"])


def assert_threshold_unchanged():
    if INCREMENTAL_SATURATION != 0.50 or INCREMENTAL_STRONG != 0.75:
        raise AnalysisRejection("preregistered efficiency thresholds were modified")


def classify(inc):
    if inc >= INCREMENTAL_STRONG:
        return "STRONG"
    if inc >= INCREMENTAL_SATURATION:
        return "PARTIAL"
    return "WEAK_OR_SATURATED"


def ladder_analysis(platform, npu, workload, cycles_by_mac, executable_by_mac):
    """cycles_by_mac / executable_by_mac keyed by preregistered MAC point."""
    assert_threshold_unchanged()
    ladder = LADDERS[(platform, npu)]
    base = ladder[0]
    out = {"platform": platform, "npu": npu, "workload": workload,
           "ladder": ladder, "rows": [], "incremental": []}
    base_ok = executable_by_mac.get(base, False)
    out["baseline_executable"] = base_ok

    if not base_ok:
        # never rebased onto a higher MAC
        out["cumulative_scaling"] = "NOT_AVAILABLE"
        out["saturation_point"] = "NOT_AVAILABLE"
        out["saturation_reason"] = "PREREGISTERED_BASELINE_NOT_EXECUTABLE"
    else:
        c0 = cycles_by_mac[base]
        for m in ladder:
            if not executable_by_mac.get(m, False):
                out["rows"].append({"mac": m, "cycles": None,
                                    "speedup": None, "cumulative_efficiency": None,
                                    "status": "NOT_EXECUTABLE"})
                continue
            c = cycles_by_mac[m]
            sp = c0 / c
            out["rows"].append({"mac": m, "cycles": c, "speedup": sp,
                                "cumulative_efficiency": sp / (m / base),
                                "status": "EXECUTABLE"})

    # incremental only between ADJACENT preregistered points, both executable
    for a, b in zip(ladder, ladder[1:]):
        if not (executable_by_mac.get(a, False) and executable_by_mac.get(b, False)):
            out["incremental"].append({"from": a, "to": b, "incremental_efficiency": None,
                                       "class": "NOT_AVAILABLE",
                                       "reason": "ADJACENT_POINT_NOT_EXECUTABLE"})
            continue
        inc = (cycles_by_mac[a] / cycles_by_mac[b]) / (b / a)
        out["incremental"].append({"from": a, "to": b, "incremental_efficiency": inc,
                                   "class": classify(inc), "reason": ""})

    if base_ok:
        sat = next((r["to"] for r in out["incremental"]
                    if r["incremental_efficiency"] is not None
                    and r["incremental_efficiency"] < INCREMENTAL_SATURATION), None)
        usable = [r for r in out["incremental"] if r["incremental_efficiency"] is not None]
        if sat is not None:
            out["saturation_point"] = sat
        elif usable:
            out["saturation_point"] = "NONE_OBSERVED"
        else:
            out["saturation_point"] = "NOT_AVAILABLE"
        out["cumulative_scaling"] = "AVAILABLE"
    out["incremental_points"] = sum(
        1 for r in out["incremental"] if r["incremental_efficiency"] is not None)
    return out


def spearman(a, b):
    """Ordinal only. Assumes no shared absolute axis."""
    n = len(a)
    if n < 2:
        return None
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return num / (da * db) if da and db else None


def rank_correlation(cfg_a, cfg_b):
    """Only over the workload subset executable in BOTH configurations."""
    shared = sorted(set(cfg_a) & set(cfg_b))
    if len(shared) < 2:
        return None, shared
    return spearman([cfg_a[w] for w in shared], [cfg_b[w] for w in shared]), shared


def trend_agreement(fvp, vela):
    """Normalized shape comparison. Absolute cycles are never subtracted or divided."""
    for k in ("absolute_error", "ratio", "calibrated_latency"):
        if k in fvp or k in vela:
            raise AnalysisRejection("absolute Vela/FVP fidelity metric is prohibited")
    return {
        "fvp_saturation_point": fvp["saturation_point"],
        "vela_saturation_point": vela["saturation_point"],
        "saturation_point_agrees": fvp["saturation_point"] == vela["saturation_point"],
        "fvp_classes": [r["class"] for r in fvp["incremental"]],
        "vela_classes": [r["class"] for r in vela["incremental"]],
        "class_agreement": sum(1 for a, b in zip(
            [r["class"] for r in fvp["incremental"]],
            [r["class"] for r in vela["incremental"]]) if a == b),
        "incremental_points": len(fvp["incremental"]),
        "speedup_rank_agreement": spearman(
            [r["speedup"] for r in fvp["rows"] if r["speedup"] is not None],
            [r["speedup"] for r in vela["rows"] if r["speedup"] is not None])
            if sum(1 for r in fvp["rows"] if r["speedup"] is not None) >= 2 else None,
    }


def assert_pmu_cross_generation(event):
    if event not in COMMON_SEMANTICS_PMU:
        raise AnalysisRejection(
            "cross-generation PMU comparison for %s (not COMMON_SEMANTICS)" % event)
    return True


def assert_no_cross_generation_cycles(npu_a, npu_b):
    if npu_a != npu_b:
        raise AnalysisRejection(
            "cross-generation raw absolute-cycle comparison (%s vs %s)" % (npu_a, npu_b))
