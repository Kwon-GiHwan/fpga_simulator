"""Generation-agnostic PMU parser for the stock MLEK profile block.

The previous parser hardcoded AXI names and silently recorded None on U85, whose
runner emits SRAM_*/EXT_* instead. This one *discovers* the emitted event set
rather than assuming it, so a generation whose names differ is visible as data
instead of as absence.
"""
import re

BLOCK_START = "Profile for Inference:"
# "INFO - NPU <name>: <value> <unit>"
EVENT_RE = re.compile(r"^\s*INFO\s*-\s*NPU\s+(?P<name>[A-Za-z0-9_]+):\s*(?P<value>\d+)\s*(?P<unit>\w+)?\s*$")


class PmuParseError(Exception):
    """Fail loudly. Never return a partially-populated record as if complete."""


def normalize(name):
    """U85 names arrive prefixed with ETHOSU_PMU_; U55/U65 do not."""
    return name[len("ETHOSU_PMU_"):] if name.startswith("ETHOSU_PMU_") else name


def parse_profile(text):
    """Return every NPU counter emitted in the first profile block."""
    i = text.find(BLOCK_START)
    if i == -1:
        raise PmuParseError("no '%s' block found" % BLOCK_START)
    events, order = {}, []
    for line in text[i:].splitlines()[1:]:
        m = EVENT_RE.match(line)
        if not m:
            if line.strip() and not line.startswith("INFO - NPU"):
                break                      # end of the contiguous NPU block
            continue
        key = normalize(m.group("name"))
        if key in events:
            raise PmuParseError("duplicate counter %s in one profile block" % key)
        events[key] = {"value": int(m.group("value")), "unit": m.group("unit"),
                       "emitted_name": m.group("name")}
        order.append(key)
    if not events:
        raise PmuParseError("profile block contained no NPU counters")
    for required in ("TOTAL", "ACTIVE", "IDLE"):
        if required not in events:
            raise PmuParseError("required counter NPU %s absent" % required)
    return {"events": events, "order": order,
            "event_set": sorted(events),
            "total": events["TOTAL"]["value"],
            "active": events["ACTIVE"]["value"],
            "idle": events["IDLE"]["value"]}


def total_identity_holds(rec):
    """IDLE is derived as TOTAL - ACTIVE in ethosu_profiler.c, so this is exact."""
    return rec["total"] == rec["active"] + rec["idle"]


def classify_generation(rec):
    s = set(rec["event_set"])
    if {"AXI0_RD_DATA_BEAT_RECEIVED", "AXI0_WR_DATA_BEAT_WRITTEN"} <= s:
        return "U55_U65_AXI_FAMILY"
    if {"SRAM_RD_DATA_BEAT_RECEIVED", "EXT_RD_DATA_BEAT_RECEIVED"} <= s:
        return "U85_SRAM_EXT_FAMILY"
    return "UNRECOGNISED_EVENT_FAMILY"
