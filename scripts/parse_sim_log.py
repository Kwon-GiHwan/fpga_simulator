#!/usr/bin/env python3
"""Vela 컴파일 로그 + FVP 시뮬 로그 → 통합 result.json.

추출 항목:
  vela_estimated_cycles    : Vela가 추정한 NPU 실행 cycles
  vela_sram_used_kb        : Vela 추정 SRAM 사용량
  vela_flash_used_kb       : Vela 추정 Flash 사용량
  fvp_npu_total_cycles     : FVP 시뮬레이터의 실제 NPU TOTAL cycles
  fvp_npu_active_cycles    : 실제 NPU ACTIVE cycles
  fvp_npu_idle_cycles      : 실제 NPU IDLE cycles

note: FVP는 사전 빌드된 mlek_img_class.axf로 실행되므로 사용자 모델과 다를 수 있음.
      vela_* metric은 사용자 모델 직접 분석 결과.
"""
import argparse
import json
import re
import sys
from pathlib import Path


VELA_PATTERNS = {
    "vela_estimated_cycles": [
        r"Total cycles\s+\(NPU\)\s+([\d,\.]+)",
        r"Inference cycles per second\s*=\s*([\d.]+)",
        r"Estimated total cycles[^\d]*([\d,]+)",
    ],
    "vela_sram_used_kb": [
        r"Total SRAM used\s*([\d.]+)\s*KiB",
        r"SRAM\s+used[^\d]*([\d.]+)\s*KiB",
    ],
    "vela_flash_used_kb": [
        r"Total\s+Off-chip Flash used\s+([\d.]+)\s*KiB",
        r"Flash\s+used[^\d]*([\d.]+)\s*KiB",
    ],
}

FVP_PATTERNS = {
    "fvp_npu_total_cycles": [r"NPU TOTAL:\s*([\d,]+)"],
    "fvp_npu_active_cycles": [r"NPU ACTIVE:\s*([\d,]+)"],
    "fvp_npu_idle_cycles": [r"NPU IDLE:\s*([\d,]+)"],
    "fvp_axi0_rd_beats": [r"NPU AXI0_RD_DATA_BEAT_RECEIVED:\s*([\d,]+)"],
    "fvp_axi0_wr_beats": [r"NPU AXI0_WR_DATA_BEAT_WRITTEN:\s*([\d,]+)"],
}


def extract(text: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).replace(",", "")
    return None


def parse_vela_summary(vela_dir: Path) -> dict:
    """Vela summary CSV에서 보조 metric 추출."""
    out: dict = {}
    for csv in vela_dir.glob("*_summary*.csv"):
        try:
            text = csv.read_text(encoding="utf-8", errors="ignore")
            # 단순 검색 — vela summary CSV 구조: header + values 한 행
            lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
            if len(lines) < 2:
                continue
            headers = [h.strip() for h in lines[0].split(",")]
            values = [v.strip() for v in lines[1].split(",")]
            row = dict(zip(headers, values))
            # 알려진 컬럼 이름 매핑
            for src, dst in [
                ("Inference cycles per second", "vela_estimated_inference_per_sec"),
                ("Total SRAM used", "vela_sram_used_kb"),
                ("Total Off-chip Flash used", "vela_flash_used_kb"),
                ("On-chip Flash used", "vela_onchip_flash_used_kb"),
            ]:
                if src in row and src.strip():
                    out[dst] = row[src]
        except Exception as e:
            print(f"warning: failed to parse {csv}: {e}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vela-log", type=Path, default=None)
    ap.add_argument("--vela-output", type=Path, default=None)
    ap.add_argument("--fvp-log", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    result: dict = {}

    # Vela 로그 파싱
    if args.vela_log and args.vela_log.exists():
        text = args.vela_log.read_text(encoding="utf-8", errors="ignore")
        for key, patterns in VELA_PATTERNS.items():
            v = extract(text, patterns)
            if v is not None:
                result[key] = v

    # Vela summary CSV 보조 파싱
    if args.vela_output and args.vela_output.exists():
        result.update(parse_vela_summary(args.vela_output))

    # FVP 로그 파싱
    if args.fvp_log and args.fvp_log.exists():
        text = args.fvp_log.read_text(encoding="utf-8", errors="ignore")
        for key, patterns in FVP_PATTERNS.items():
            v = extract(text, patterns)
            if v is not None:
                result[key] = v

    # 빈 값을 N/A로 정규화
    keys = (
        list(VELA_PATTERNS.keys())
        + list(FVP_PATTERNS.keys())
        + ["vela_estimated_inference_per_sec", "vela_onchip_flash_used_kb"]
    )
    final = {k: result.get(k, "N/A") for k in keys}

    args.output.write_text(json.dumps(final, indent=2, ensure_ascii=False))
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
