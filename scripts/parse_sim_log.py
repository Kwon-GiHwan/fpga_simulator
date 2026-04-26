#!/usr/bin/env python3
"""FVP 시뮬 로그와 Vela 출력에서 metric 추출 → result.json.

robust 처리: 일부 metric만 추출되어도 가능한 만큼 기록.
"""
import argparse
import json
import re
import sys
from pathlib import Path


# FVP / Ethos-U 표준 출력 패턴
PATTERNS = {
    "total_cycles": [
        r"Total cycles:\s*([\d,]+)",
        r"NPU TOTAL[^\d]*([\d,]+)",
        r"Total Cycles[^\d]*([\d,]+)",
    ],
    "inference_time_ms": [
        r"Inference time[^\d]*([\d.]+)\s*ms",
        r"Inference\s*\(.*\):\s*([\d.]+)\s*ms",
    ],
    "sram_used_kb": [
        r"SRAM\s+used[^\d]*([\d.]+)\s*KiB",
        r"sram_used\s*=\s*([\d.]+)",
    ],
    "flash_used_kb": [
        r"Flash\s+used[^\d]*([\d.]+)\s*KiB",
        r"flash_used\s*=\s*([\d.]+)",
    ],
}


def extract(text: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).replace(",", "")
    return None


def parse_vela_summary(vela_dir: Path) -> dict:
    """Vela가 생성한 .csv summary가 있으면 partial metric 추출."""
    out = {}
    for csv in vela_dir.glob("*_summary*.csv"):
        try:
            text = csv.read_text(encoding="utf-8", errors="ignore")
            if "SRAM" in text and "sram_used_kb" not in out:
                # CSV는 line 단위로 다양한 포맷. 단순 regex로 시도.
                m = re.search(r"SRAM[^,]*,\s*([\d.]+)", text)
                if m:
                    out["sram_used_kb"] = m.group(1)
        except Exception as e:
            print(f"warning: failed to parse {csv}: {e}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fvp-log", type=Path, default=None,
                    help="FVP 시뮬 로그 파일 (없으면 vela-only)")
    ap.add_argument("--vela-output", type=Path, default=None,
                    help="Vela --output-dir 경로 (summary.csv 보조 파싱)")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    result: dict = {
        "total_cycles": None,
        "inference_time_ms": None,
        "sram_used_kb": None,
        "flash_used_kb": None,
    }

    if args.fvp_log and args.fvp_log.exists():
        log_text = args.fvp_log.read_text(encoding="utf-8", errors="ignore")
        for key, patterns in PATTERNS.items():
            v = extract(log_text, patterns)
            if v is not None:
                result[key] = v

    if args.vela_output and args.vela_output.exists():
        vela_metrics = parse_vela_summary(args.vela_output)
        for k, v in vela_metrics.items():
            if result.get(k) is None:
                result[k] = v

    # 빈 값은 "N/A"로 정규화
    final = {k: (v if v is not None else "N/A") for k, v in result.items()}

    args.output.write_text(json.dumps(final, indent=2, ensure_ascii=False))
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
