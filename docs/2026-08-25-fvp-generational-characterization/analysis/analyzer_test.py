"""Attack the analysis rules with synthetic fixtures before real evidence.

Every prohibition must actually fire. A rule that cannot reject is decoration.
"""
import sys
sys.path.insert(0, "/tmp/xqbin")
import analyzer as A

R = {}

def ok(name, cond): R[name] = bool(cond)

# fixtures -------------------------------------------------------------------
def rec(c1, c2=None, c3=None, cid="fixture"):
    base = {"status": "SUCCESS", "inference_count_line": 1, "npu_active_cycles": 1,
            "npu_idle_cycles": 1, "axi0_rd_beats": 1, "axi0_wr_beats": 1, "axi1_rd_beats": 1}
    mk = lambda c: dict(base, npu_total_cycles=c)
    return {"cell_id": cid, "M1": mk(c1), "M2": mk(c2 if c2 is not None else c1),
            "M3": mk(c3 if c3 is not None else c1)}

# N1 M1 != M2 -> reject
try:
    A.canonical_value(rec(1000, 1001)); ok("N1_M1_ne_M2_rejected", False)
except A.AnalysisRejection: ok("N1_M1_ne_M2_rejected", True)
ok("N1_equal_accepted", A.canonical_value(rec(1000)) == 1000)

# N2 TA-OFF cell in primary -> reject
try:
    A.assert_primary({"cell_id": "x", "platform": "SSE-310", "timing_adapter": "OFF"})
    ok("N2_ta_off_rejected", False)
except A.AnalysisRejection: ok("N2_ta_off_rejected", True)
try:
    A.assert_primary({"cell_id": "x", "platform": "SSE-300", "timing_adapter": "ON"})
    ok("N2_ta_on_accepted", True)
except A.AnalysisRejection: ok("N2_ta_on_accepted", False)

# N3 non-executable gap must not be bridged (wav2letter/SSE-300/U55 shape)
cyc = {32: None, 64: None, 128: None, 256: 1_000_000}
ex = {32: False, 64: False, 128: False, 256: True}
r = A.ladder_analysis("SSE-300", "ethos-u55", "wav2letter_pruned_int8", cyc, ex)
ok("N3_gap_not_bridged", r["incremental_points"] == 0)
ok("N3_cumulative_not_available", r["cumulative_scaling"] == "NOT_AVAILABLE")
ok("N3_saturation_not_available", r["saturation_point"] == "NOT_AVAILABLE")
ok("N3_no_rebase_to_256", all(row["speedup"] is None for row in r["rows"]))

# N4 middle gap: 128 exec, 256 non-exec, 512 exec -> 128->512 must NOT be a step
cyc2 = {128: 800, 256: None, 512: 200, 1024: 100, 2048: 60}
ex2 = {128: True, 256: False, 512: True, 1024: True, 2048: True}
r2 = A.ladder_analysis("SSE-320", "ethos-u85", "synthetic", cyc2, ex2)
steps = [(x["from"], x["to"]) for x in r2["incremental"] if x["incremental_efficiency"] is not None]
ok("N4_no_bridged_step", (128, 512) not in steps)
ok("N4_adjacent_only", all((a, b) in [(128,256),(256,512),(512,1024),(1024,2048)] for a, b in steps))

# N5 threshold tampering -> reject
orig = A.INCREMENTAL_SATURATION
A.INCREMENTAL_SATURATION = 0.40
try:
    A.assert_threshold_unchanged(); ok("N5_threshold_change_rejected", False)
except A.AnalysisRejection: ok("N5_threshold_change_rejected", True)
A.INCREMENTAL_SATURATION = orig

# N6 cross-generation raw cycle comparison -> reject
try:
    A.assert_no_cross_generation_cycles("ethos-u55", "ethos-u85")
    ok("N6_cross_gen_cycles_rejected", False)
except A.AnalysisRejection: ok("N6_cross_gen_cycles_rejected", True)
ok("N6_same_gen_accepted", A.assert_no_cross_generation_cycles("ethos-u85", "ethos-u85") is None)

# N7 Vela/FVP absolute fidelity metric -> reject
try:
    A.trend_agreement({"ratio": 1.2}, {}); ok("N7_absolute_ratio_rejected", False)
except A.AnalysisRejection: ok("N7_absolute_ratio_rejected", True)

# N8 PMU cross-generation outside COMMON_SEMANTICS -> reject
try:
    A.assert_pmu_cross_generation("NPU_ACTIVE"); ok("N8_npu_active_rejected", False)
except A.AnalysisRejection: ok("N8_npu_active_rejected", True)
try:
    A.assert_pmu_cross_generation("AXI0_RD_DATA_BEAT_RECEIVED"); ok("N8_axi_rejected", False)
except A.AnalysisRejection: ok("N8_axi_rejected", True)
ok("N8_cycle_accepted", A.assert_pmu_cross_generation("CYCLE"))

# N9 ranking must use only the shared executable subset
a = {"w1": 10, "w2": 20, "w3": 30}
b = {"w1": 11, "w2": 21}
rho, shared = A.rank_correlation(a, b)
ok("N9_shared_subset_only", shared == ["w1", "w2"])

# P1 positive: perfect linear scaling -> STRONG, NONE_OBSERVED
cyc3 = {128: 800, 256: 400, 512: 200, 1024: 100, 2048: 50}
ex3 = {m: True for m in cyc3}
r3 = A.ladder_analysis("SSE-320", "ethos-u85", "linear", cyc3, ex3)
ok("P1_linear_all_strong", all(x["class"] == "STRONG" for x in r3["incremental"]))
ok("P1_linear_none_observed", r3["saturation_point"] == "NONE_OBSERVED")
ok("P1_cumulative_one", abs(r3["rows"][-1]["cumulative_efficiency"] - 1.0) < 1e-9)

# P2 boundary: flat cycles across a 2x MAC step is EXACTLY 0.50.
# The frozen rule makes that PARTIAL (0.50 <= x < 0.75) and saturation strictly < 0.50.
cyc4 = {128: 800, 256: 800, 512: 800, 1024: 800, 2048: 800}
r4 = A.ladder_analysis("SSE-320", "ethos-u85", "flat", cyc4, {m: True for m in cyc4})
ok("P2_boundary_exactly_half_is_partial", r4["incremental"][0]["class"] == "PARTIAL")
ok("P2_boundary_half_not_saturation", r4["saturation_point"] == "NONE_OBSERVED")
ok("P2_boundary_value_is_half", abs(r4["incremental"][0]["incremental_efficiency"] - 0.50) < 1e-12)

# P3 genuine saturation: cycles worsen slightly -> strictly below 0.50
cyc5 = {128: 800, 256: 810, 512: 820, 1024: 830, 2048: 840}
r5 = A.ladder_analysis("SSE-320", "ethos-u85", "saturating", cyc5, {m: True for m in cyc5})
ok("P3_saturates_at_first_sub_half", r5["saturation_point"] == 256)
ok("P3_first_step_weak", r5["incremental"][0]["class"] == "WEAK_OR_SATURATED")
ok("P3_below_half", r5["incremental"][0]["incremental_efficiency"] < 0.50)

for k in sorted(R): print("  %-38s %s" % (k, "PASS" if R[k] else "FAIL"))
print("ALL_PASS" if all(R.values()) else "SOME_FAILED")
