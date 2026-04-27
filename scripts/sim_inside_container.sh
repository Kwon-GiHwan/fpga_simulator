#!/usr/bin/env bash
# 컨테이너 내부 실행: 사용자 .tflite → Vela 컴파일 → FVP 동적 로드 → 결과 파싱
#
# 입력: /sim/input.tflite (호스트 fetch_model.sh가 준비)
# 출력:
#   /sim/result.json — 통합 metric (vela 추정 + FVP 사용자 모델 실측)
#   /sim/sim_result.log — FVP raw 로그 (호스트로 docker logs로도 동시 기록)
#
# 동작 방식:
#   1. vela로 사용자 모델을 ethos-u 호환 형태로 컴파일
#   2. mlek_inference_runner.axf (DYNAMIC_MEM_LOAD=ON 빌드)를 FVP에서 실행하면서
#      vela 컴파일된 모델을 메모리 0x90000000에 inject
#      → 사용자 모델로 실제 NPU TOTAL/ACTIVE/IDLE 측정
set -euo pipefail

IN_MODEL=/sim/input.tflite
OUT_DIR=/sim/output
mkdir -p "$OUT_DIR"

[[ -f "$IN_MODEL" ]] || { echo "input model missing: $IN_MODEL" >&2; exit 1; }

# 사전 빌드된 inference_runner — DYNAMIC_MEM_LOAD_ENABLED=ON
INFERENCE_RUNNER_AXF=/opt/arm/ml-embedded-evaluation-kit/build-dynamic/bin/mlek_inference_runner.axf

# DYNAMIC_MODEL_BASE 주소 (mps3 platform CMakeLists.txt 정의값)
MODEL_BASE_ADDR=0x90000000

# ============================================================================
# 1. Vela 컴파일 — 사용자 모델의 cycle/SRAM/Flash 추정값 + ethos-u 호환 .tflite 산출
# ============================================================================
echo "=== [Vela] compiling user model (ethos-u55-128) ==="
vela "$IN_MODEL" \
  --accelerator-config ethos-u55-128 \
  --output-dir "$OUT_DIR" 2>&1 | tee /sim/vela.log

VELA_OUT=$(ls "$OUT_DIR"/*_vela.tflite 2>/dev/null | head -n1 || true)
if [[ -z "$VELA_OUT" ]]; then
  echo "ERROR: vela 컴파일 산출물(*_vela.tflite)이 없음" >&2
  # vela 단독 결과만으로 result.json 작성 (FVP 단계 skip)
  python3 /scripts/parse_sim_log.py \
    --vela-log /sim/vela.log \
    --vela-output "$OUT_DIR" \
    --output /sim/result.json
  exit 1
fi
echo "vela output: $VELA_OUT  ($(stat -c '%s' "$VELA_OUT") bytes)"

# ============================================================================
# 2. FVP 실행 — inference_runner.axf + vela 컴파일된 사용자 모델을 메모리 inject
#    → 사용자 모델 기준 NPU TOTAL/ACTIVE/IDLE cycles 실측
# ============================================================================
if [[ ! -f "$INFERENCE_RUNNER_AXF" ]]; then
  echo "WARNING: $INFERENCE_RUNNER_AXF not found — FVP 단계 skip (vela 결과만 반환)" >&2
  python3 /scripts/parse_sim_log.py \
    --vela-log /sim/vela.log \
    --vela-output "$OUT_DIR" \
    --output /sim/result.json
  exit 0
fi

echo "=== [FVP] running inference_runner.axf with user model @ ${MODEL_BASE_ADDR} ==="
FVP_Corstone_SSE-300_Ethos-U55 \
  -a "$INFERENCE_RUNNER_AXF" \
  --data "${VELA_OUT}@${MODEL_BASE_ADDR}" \
  -C ethosu.num_macs=128 \
  -C mps3_board.visualisation.disable-visualisation=1 \
  -C mps3_board.uart0.out_file=- \
  --stat \
  --timelimit 300 \
  > /sim/fvp.log 2>&1 || true

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
