# NPU-server Runner 등록

> 대상 서버: `gihwan-local` (현재 model_compression runner와 동일 서버, **별도 디렉토리**)  
> 미래 서버 분리 시: 별도 머신에 동일 절차 + `~/.npu-sim.env`의 `IMAGE`/`SIM_WORK_DIR` 조정

## 절차

### 1. 작업 디렉토리

```bash
ssh gihwan-local
mkdir -p ~/actions-runner-npu && cd ~/actions-runner-npu
```

### 2. Runner 바이너리

이미 model_compression runner를 위해 받아둔 tarball 재사용 가능:

```bash
cp ~/actions-runner/actions-runner-linux-x64-*.tar.gz . 2>/dev/null \
  || curl -o actions-runner-linux-x64.tar.gz -L \
       "https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz"
tar xzf actions-runner-linux-x64*.tar.gz
```

### 3. fpga_simulator 리포 등록 토큰 발급

GitHub: `Kwon-GiHwan/fpga_simulator` → Settings → Actions → Runners → New self-hosted runner → Linux x64.

### 4. config

```bash
./config.sh \
  --url https://github.com/Kwon-GiHwan/fpga_simulator \
  --token <REGISTRATION_TOKEN_FROM_GITHUB_UI> \
  --name gihwan-local-npu-runner \
  --labels self-hosted,linux,x64,npu-server \
  --work _work \
  --unattended
```

### 5. systemd 서비스

```bash
sudo ./svc.sh install gihwan
sudo ./svc.sh start
sudo ./svc.sh status
```

### 6. Docker 권한 (이미 model_compression 등록 시 적용했으면 스킵)

```bash
sudo usermod -aG docker gihwan
sudo ./svc.sh stop && sudo ./svc.sh start
```

### 7. 서버 `.env` 작성

```bash
cat > /home/gihwan/.npu-sim.env <<'EOF'
IMAGE=fpga-simulator:latest
SIM_WORK_DIR=/home/gihwan/npu-sim-work
SOURCE_REPO_COMMENT_TOKEN=ghp_여기에토큰
EOF
chmod 600 /home/gihwan/.npu-sim.env
```

### 8. SOURCE_REPO_COMMENT_TOKEN 발급

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens

- Repository access: `Kwon-GiHwan/model_compression`
- Permissions:
  - Pull requests: Read and write (PR 댓글)
  - Issues: Read and write (commit comment fallback)
  - Contents: Read

### 9. Docker 이미지 빌드 (1회)

```bash
cd ~/fpga_simulator   # 또는 워크스페이스 어디든
docker build -t fpga-simulator:latest .
docker images | grep fpga-simulator
```

## 서버 분리로 이전 시 변경 사항

미래에 NPU 시뮬을 별도 서버로 옮길 경우:

1. 새 서버에서 위 1~9 단계 동일 수행 (라벨은 그대로 `npu-server` 유지)
2. 모델 파일 공유 메커니즘 결정:
   - **S3**: model_compression의 train.sh에 S3 업로드 단계 추가 + train.yml dispatch 시 `model_path=s3://...`
   - **HTTP**: 사내 파일 서버 등 — `model_path=https://...`
3. fpga_simulator는 코드 변경 없음. `fetch_model.sh`가 자동 분기.
