#!/usr/bin/env bash
# 컨테이너 내부 실행: 사용자 .tflite → Vela 컴파일 → FVP 시뮬 → 결과 파싱
#
# 입력: /sim/input.tflite (호스트 fetch_model.sh가 준비)
# 출력:
#   /sim/result.json — 통합 metric (vela 추정 + FVP 실측)
#   /sim/sim_result.log — FVP 원본 로그 (호스트로 docker logs로도 동시 기록)
set -euo pipefail

IN_MODEL=/sim/input.tflite
OUT_DIR=/sim/output
mkdir -p "$OUT_DIR"

[[ -f "$IN_MODEL" ]] || { echo "input model missing: $IN_MODEL" >&2; exit 1; }

# 사전 빌드된 .axf (이미지에 영구 포함됨, ethos-u55-128 / MPS3 SSE-300 / GNU)
PREBUILT_AXF=/opt/arm/ml-embedded-evaluation-kit/cmake-build-mps3-sse-300-ethos-u55-128-gnu-tflm/bin/mlek_img_class.axf

# ============================================================================
# 1. Vela 컴파일 — 사용자 모델의 cycle/SRAM/Flash 추정값
# ============================================================================
echo "=== [Vela] compiling user model ==="
vela "$IN_MODEL" \
  --accelerator-config ethos-u55-128 \
  --output-dir "$OUT_DIR" 2>&1 | tee /sim/vela.log

VELA_OUT=$(ls "$OUT_DIR"/*_vela.tflite 2>/dev/null | head -n1 || true)
echo "vela output: ${VELA_OUT:-none}"

# ============================================================================
# 2. FVP 실행 — 사전 빌드된 mlek_img_class.axf로 실제 NPU cycle 측정
#    (참고: 사용자 모델을 .axf로 통합하려면 use_case 빌드가 필요하나
#     매 run 30분이라 비현실적. 사전 빌드된 .axf로 NPU 실측값 제공.)
# ============================================================================
if [[ -f "$PREBUILT_AXF" ]]; then
  echo "=== [FVP] running mlek_img_class.axf ==="
  FVP_Corstone_SSE-300_Ethos-U55 \
    -a "$PREBUILT_AXF" \
    -C ethosu.num_macs=128 \
    -C mps3_board.visualisation.disable-visualisation=1 \
    -C mps3_board.uart0.out_file=- \
    --stat \
    --timelimit 300 \
    > /sim/fvp.log 2>&1 || true
else
  echo "WARNING: pre-built axf not found at $PREBUILT_AXF — FVP step skipped" >&2
fi

# ============================================================================
# 3. 로그 파싱 → result.json
# ============================================================================
echo "=== [Parse] generating result.json ==="
python3 /scripts/parse_sim_log.py \
  --vela-log /sim/vela.log \
  --vela-output "$OUT_DIR" \
  --fvp-log /sim/fvp.log \
  --output /sim/result.json

cat /sim/result.json
echo "=== Done ==="
