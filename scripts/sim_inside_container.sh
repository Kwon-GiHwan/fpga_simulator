#!/usr/bin/env bash
# 컨테이너 내부에서 실행: Vela → MLEK 빌드 → FVP 시뮬 → 로그 파싱
# 호스트의 작업 디렉토리는 /sim 에 마운트되어 있음.
#   /sim/input.tflite : 입력 모델 (호스트 fetch_model.sh가 준비)
#   /sim/result.json : 출력 (이 스크립트가 생성)
#   /sim/sim_result.log : FVP raw 로그 (docker logs로 호스트에 동시 기록됨)
set -euo pipefail

IN_MODEL=/sim/input.tflite
OUT_DIR=/sim/output
mkdir -p "$OUT_DIR"

[[ -f "$IN_MODEL" ]] || { echo "input model missing: $IN_MODEL" >&2; exit 1; }

# 1. Vela 컴파일
echo "=== [Vela] compiling ==="
vela "$IN_MODEL" \
  --accelerator-config ethos-u55-128 \
  --output-dir "$OUT_DIR"

# Vela 결과 파일 (보통 입력파일명_vela.tflite 패턴)
VELA_OUT=$(ls "$OUT_DIR"/*_vela.tflite | head -n1)
echo "vela output: $VELA_OUT"

# 2. MLEK 펌웨어 빌드 (use_case: img_class를 기본 — 단순 동작 확인용)
#    실제 use_case는 추후 client_payload에 use_case 필드 받아 처리.
echo "=== [MLEK] building firmware ==="
cd /opt/arm/ml-embedded-evaluation-kit

# build_default.py 호출. 모델 경로를 use_case 빌드에 주입하는 방식은
# MLEK의 표준 cmake 옵션(-D<USECASE>_MODEL_TFLITE_PATH=...)을 사용한다.
# 단순화를 위해 기본 모델로 빌드 — 실제 모델 통합은 향후 use_case 매핑 추가 시 확장.
# 현재는 vela 컴파일 결과 검증 + MLEK 기본 펌웨어 빌드 가능 여부만 확인.
python3 build_default.py --npu-config-name ethos-u55-128 --target-platform mps3 || {
  echo "MLEK build failed — vela 컴파일까지는 성공. 펌웨어 빌드는 추후 use_case 매핑 추가 필요." >&2
  # 빌드 실패해도 vela 결과만으로 metric 일부 추출 가능 (vela 자체 출력)
  # 그러나 cycle/SRAM은 FVP 실행이 필요하므로 아래 단계 스킵 후 Vela 결과만 반환
  python3 /scripts/parse_sim_log.py --vela-output "$OUT_DIR" --output /sim/result.json
  exit 0
}

# 3. FVP 실행
echo "=== [FVP] running simulation ==="
ELF=$(find build -name '*.axf' -o -name '*.elf' | head -n1)
[[ -n "$ELF" ]] || { echo "ELF not found in build/" >&2; exit 1; }

FVP_Corstone_SSE-300_Ethos-U55 \
  -a "$ELF" \
  -C ethosu.num_macs=128 \
  -C mps3_board.visualisation.disable-visualisation=1 \
  -C mps3_board.uart0.out_file=- \
  --stat \
  --timelimit 600 \
  > /sim/fvp.log 2>&1 || true

# 4. 로그 파싱
echo "=== [Parse] generating result.json ==="
python3 /scripts/parse_sim_log.py \
  --fvp-log /sim/fvp.log \
  --vela-output "$OUT_DIR" \
  --output /sim/result.json

cat /sim/result.json
echo "=== Done ==="
