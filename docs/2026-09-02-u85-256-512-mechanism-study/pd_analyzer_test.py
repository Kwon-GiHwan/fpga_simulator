#!/usr/bin/env python3
"""Mutation/negative tests for pd_analyzer v2 (debug_db mapping)."""
import os
import tempfile
import unittest

import pd_analyzer as A


def prof(records, tail_total):
    """records: list of (ccnt, evt5, hist)."""
    lines = ["PLPROF_BEGIN,%d" % len(records)]
    for i, (c, e, h) in enumerate(records):
        lines.append("PLPROF,%d,%d,%s,0x%04X" % (i, c, ",".join(map(str, e)), h))
    lines.append("PLPROF_FINAL_HIST,0xFFFF")
    lines.append("PLPROF_END")
    return {"plprof": "\n".join(lines), "pl_count": len(records),
            "total": tail_total}


class TestUnits(unittest.TestCase):
    def test_ring_decode_with_tail(self):
        # windows: [0,1], [2], remainder [3] -> tail
        p = prof([(50, [1] * 5, 0x0003), (60, [2] * 5, 0x0004)], 70)
        u = A.units(p, 4)
        self.assertEqual([x["launches"] for x in u], [[0, 1], [2], [3]])
        self.assertTrue(u[2]["tail"])
        self.assertEqual(u[2]["ccnt"], 70)

    def test_ring_wrap(self):
        # 17 launches: first window bits 0..15 (16 launches), then bit 0 again
        p = prof([(10, [0] * 5, 0xFFFF), (20, [0] * 5, 0x0001)], 99)
        u = A.units(p, 17)
        self.assertEqual(u[0]["launches"], list(range(16)))
        self.assertEqual(u[1]["launches"], [16])
        self.assertEqual(len(u), 2)

    def test_noncontiguous_rejects(self):
        p = prof([(10, [0] * 5, 0x0005)], 9)      # bits 0 and 2: gap
        with self.assertRaises(A.Reject):
            A.units(p, 9)

    def test_overflow_rejects(self):
        p = prof([(10, [0] * 5, 0x0003)], 9)      # decodes 2 > inserted 1
        with self.assertRaises(A.Reject):
            A.units(p, 1)

    def test_plcount_mismatch_rejects(self):
        p = prof([(10, [0] * 5, 0x0001)], 9)
        p["pl_count"] = 3
        with self.assertRaises(A.Reject):
            A.units(p, 2)


class TestPerSource(unittest.TestCase):
    def cell(self, records, tail, launch_map):
        return {"launch_map": launch_map, "source": {},
                "prof": prof(records, tail)}

    def test_exact_and_mixed(self):
        # launches: L0->srcA, L1->srcA, L2->srcB, L3->srcB
        # units: [L0,L1] (pure A), [L2] (pure B), tail [L3] (pure B)
        agg, urows = A.per_source(self.cell(
            [(100, [1] * 5, 0x0003), (200, [2] * 5, 0x0004)], 300,
            [7, 7, 8, 8]))
        self.assertEqual(agg[7]["ccnt"], 100)
        self.assertEqual(agg[8]["ccnt"], 500)     # 200 + tail 300
        self.assertTrue(agg[8]["tail_in_op"])
        self.assertEqual(len(urows), 3)

    def test_mixed_unit_not_separated(self):
        agg, urows = A.per_source(self.cell(
            [(100, [1] * 5, 0x0003)], 999, [7, 8]))
        self.assertIsNone(agg[7]["ccnt"])
        self.assertIsNone(agg[8]["ccnt"])
        self.assertEqual(urows[0]["source_ids"], [7, 8])

    def test_sync_pseudo_op_window(self):
        # window mixing a real op with a KERNEL_WAIT: membership recorded,
        # op becomes NOT_SEPARATED, SYNC id present in unit row
        agg, urows = A.per_source(self.cell(
            [(100, [1] * 5, 0x0003)], 999, [7, A.SYNC_SID]))
        self.assertIsNone(agg[7]["ccnt"])
        self.assertIn(A.SYNC_SID, urows[0]["source_ids"])

    def test_none_prof(self):
        c = {"prof": None}
        self.assertEqual(A.per_source(c), (None, None))


class TestParseDb(unittest.TestCase):
    XML = """<x><table name="queue">
<![CDATA[
"offset","cmdstream_id","optimised_id","scheduled_id"
300,1,2,9
100,1,1,8
]]>
</table><table name="optimised">
<![CDATA[
"id","source_id","operator","kernel_w","kernel_h","ofm_w","ofm_h","ofm_d"
1,7,"Conv2D",3,3,4,4,8
2,7,"Rescale",1,1,4,4,8
]]>
</table><table name="source">
<![CDATA[
"id","operator","kernel_w","kernel_h","ofm_w","ofm_h","ofm_d","ext_key"
7,"Conv2D",3,3,4,4,8,"2"
]]>
</table></x>"""

    def test_queue_sorted_by_offset(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False)
        f.write(self.XML); f.close()
        q, opt, src = A.parse_db(f.name)
        os.unlink(f.name)
        self.assertEqual(q, [(100, 1), (300, 2)])
        self.assertEqual(opt[2]["source_id"], 7)
        self.assertEqual(src[7]["ofm"], "4x4x8")

    def test_missing_table_rejects(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False)
        f.write("<x></x>"); f.close()
        with self.assertRaises(A.Reject):
            A.parse_db(f.name)
        os.unlink(f.name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
