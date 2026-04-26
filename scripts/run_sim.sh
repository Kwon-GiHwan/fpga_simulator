#!/usr/bin/env bash
# 호스트 측 시뮬레이션 래퍼.
# - fetch_model.sh로 모델을 작업 디렉토리에 복사/다운로드
# - Docker 컨테이너 안에서 vela 컴파일 → MLEK 빌드 → FVP 실행 → 결과 파싱
#
# 사용: bash scripts/run_sim.sh <MODEL_SRC> <COMMIT_SHA>
set -euo pipefail

MODEL_SRC="${1:?MODEL_SRC required (절대경로 / s3:// / https://)}"
COMMIT_SHA="${2:?COMMIT_SHA required}"
SHORT_SHA="${COMMIT_SHA:0:8}"

# 환경변수 (워크플로우에서 주입)
: "${IMAGE:?IMAGE not set}"
: "${SIM_WORK_DIR:?SIM_WORK_DIR not set}"

WORK_DIR="${SIM_WORK_DIR}/${COMMIT_SHA}"
CONTAINER_NAME="npu-sim-${SHORT_SHA}"
LOG_FILE="${WORK_DIR}/sim_result.log"

mkdir -p "$WORK_DIR"

echo "[run_sim] commit=$COMMIT_SHA  src=$MODEL_SRC  workdir=$WORK_DIR"

# 1. 모델 가져오기 (로컬/S3/HTTP 추상화)
bash "$(dirname "$0")/fetch_model.sh" "$MODEL_SRC" "${WORK_DIR}/input.tflite"

# 2. 잔존 컨테이너 정리
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

# 3. 컨테이너 안에서 vela → build → FVP → parse 일괄 실행
#    호스트의 WORK_DIR을 컨테이너 /sim 으로 마운트
#    호스트의 scripts/를 컨테이너 /scripts 로 마운트 (sim_inside_container.sh, parse_sim_log.py 사용)
SCRIPTS_HOST="$(cd "$(dirname "$0")" && pwd)"

docker run -d \
  --name "$CONTAINER_NAME" \
  -v "${WORK_DIR}:/sim" \
  -v "${SCRIPTS_HOST}:/scripts:ro" \
  -e COMMIT_SHA="$COMMIT_SHA" \
  "$IMAGE" \
  bash /scripts/sim_inside_container.sh

# 4. 로그 실시간 파일 + stdout
docker logs -f "$CONTAINER_NAME" 2>&1 | tee "$LOG_FILE" &
LOG_PID=$!

EXIT_CODE="$(docker wait "$CONTAINER_NAME")"
wait "$LOG_PID" 2>/dev/null || true

docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true

if [[ "$EXIT_CODE" -ne 0 ]]; then
  echo "[run_sim] simulation failed (exit $EXIT_CODE)" >&2
  exit "$EXIT_CODE"
fi

# 5. result.json 검증
if [[ ! -f "${WORK_DIR}/result.json" ]]; then
  echo "[run_sim] ERROR: result.json missing after sim" >&2
  exit 1
fi

echo "[run_sim] OK"
