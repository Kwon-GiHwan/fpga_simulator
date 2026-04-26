#!/usr/bin/env bash
# 모델 소스 추상화 — 같은 서버 / 분리 서버 모두 지원.
#
# 사용: fetch_model.sh <SRC> <DEST>
#   SRC 형식별 동작:
#     /abs/path/...      → cp (현재 같은 서버 시나리오)
#     s3://bucket/key    → aws s3 cp (서버 분리 시)
#     http://, https://  → curl (서버 분리 시)
#
# 미래에 서버를 분리해도 이 스크립트만 인식하면 코드 변경 0.
set -euo pipefail

SRC="${1:?source path/url required}"
DEST="${2:?destination path required}"

mkdir -p "$(dirname "$DEST")"

case "$SRC" in
  s3://*)
    command -v aws >/dev/null 2>&1 || { echo "aws CLI not found" >&2; exit 1; }
    echo "[fetch_model] s3 → $DEST"
    aws s3 cp "$SRC" "$DEST"
    ;;
  http://*|https://*)
    echo "[fetch_model] http → $DEST"
    curl -fsSL "$SRC" -o "$DEST"
    ;;
  /*)
    echo "[fetch_model] local cp → $DEST"
    [[ -f "$SRC" ]] || { echo "local file not found: $SRC" >&2; exit 1; }
    cp "$SRC" "$DEST"
    ;;
  *)
    echo "Unsupported source scheme: $SRC" >&2
    echo "  지원 형식: /absolute/path | s3://... | http(s)://..." >&2
    exit 1
    ;;
esac

[[ -s "$DEST" ]] || { echo "fetched file is empty: $DEST" >&2; exit 1; }
echo "[fetch_model] OK — $(stat -c '%s' "$DEST") bytes"
