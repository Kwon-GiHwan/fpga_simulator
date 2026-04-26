# FPGA Simulator (NPU Sim Pipeline)

`Kwon-GiHwan/model_compression`에서 생성된 `.tflite` 모델을 받아 **Vela 컴파일 → MLEK 펌웨어 빌드 → FVP(Corstone SSE-300) 시뮬레이션** 후 결과를 source repo에 PR/commit 댓글로 회신하는 자동화 파이프라인.

## 동작 흐름

```
[model_compression] push → 학습 → .tflite 산출
    ↓ repository_dispatch (event_type=new_model_ready)
[fpga_simulator runner] receives → run_sim.sh
    ↓ Vela compile → MLEK build → FVP → parse
    ↓ result.json
    ↓ POST PR/commit comment back to model_compression
```

## 같은 서버 / 분리 서버 모두 지원

핵심: `scripts/fetch_model.sh`가 `client_payload.model_path` 형식을 자동 감지.

| model_path 형식 | 동작 | 전제 |
|---|---|---|
| `/abs/path/model.tflite` | `cp` | 두 runner가 같은 서버 |
| `s3://bucket/model.tflite` | `aws s3 cp` | 분리 서버 + S3 권한 |
| `https://...` | `curl` | 분리 서버 + HTTP 접근 |

→ 미래에 서버를 분리해도 model_compression이 보내는 `model_path` 형식만 바꾸면 됨, 본 프로젝트 코드 변경 0.

## 사전 준비

1. **Docker 이미지 빌드** (서버에서)
   ```bash
   docker build -t fpga-simulator:latest .
   ```

   > **아키텍처 노트**: 현재 Dockerfile은 x86_64 호스트용입니다. FVP tarball은 컨테이너 빌드 시
   > ARM Developer 사이트에서 자동 다운로드됩니다 (등록 없이 받을 수 있는 다이렉트 링크 사용).
   > ARM64 호스트로 이전 시 base image를 `arm64v8/ubuntu:22.04`로, FVP tarball/toolchain을
   > ARM64 빌드로 교체하면 됩니다 (.devcontainer 시절 ARM tarball은 디렉토리에 보존되어 있음).

2. **Self-hosted runner 등록** — `docs/runner-setup.md` 참조 (라벨: `npu-server`)

3. **서버 `.env` 작성**
   ```bash
   cp .env.example /home/gihwan/.npu-sim.env
   # 토큰값 채우고
   chmod 600 /home/gihwan/.npu-sim.env
   ```

## 수동 테스트

```bash
# Actions UI → NPU Simulation Pipeline → Run workflow → 입력 채우기
#  - commit:      <임의 sha>
#  - model_path:  /home/user/models/model_<sha>.tflite
#  - source_repo: Kwon-GiHwan/model_compression
```

또는 CLI:
```bash
gh workflow run sim_pipeline.yml \
  -f commit=abc123 \
  -f model_path=/home/user/models/model_abc123.tflite \
  -f source_repo=Kwon-GiHwan/model_compression
```

## 결과 형식

`result.json`:
```json
{
  "total_cycles": "1240500",
  "inference_time_ms": "12.4",
  "sram_used_kb": "256.5",
  "flash_used_kb": "1024.0"
}
```

source repo PR/commit 댓글:
```
🚀 NPU Simulation Result

| Metric | Value |
|--------|-------|
| Total Cycles | 1,240,500 |
| Inference Time | 12.4 ms |
| ... |
```

## 환경변수 (서버 .env)

| Name | 설명 |
|------|------|
| `IMAGE` | Docker 이미지 태그 (예: `fpga-simulator:latest`) |
| `SIM_WORK_DIR` | 시뮬 작업 디렉토리 (예: `/home/gihwan/npu-sim-work`) |
| `SOURCE_REPO_COMMENT_TOKEN` | source repo 코멘트 작성 권한 PAT |

## 프로젝트 구조

```
.
├── Dockerfile                  # ARM64 + FVP + Vela + MLEK
├── scripts/
│   ├── run_sim.sh              # 호스트 측 docker 래퍼
│   ├── sim_inside_container.sh # 컨테이너 내부: vela → build → FVP → parse
│   ├── fetch_model.sh          # 모델 소스 추상화 (local/s3/http)
│   └── parse_sim_log.py        # FVP/Vela 로그 → result.json
├── .github/workflows/
│   └── sim_pipeline.yml        # repository_dispatch 수신
├── docs/
│   └── runner-setup.md         # npu-server runner 등록
└── .env.example
```

## License

MIT
