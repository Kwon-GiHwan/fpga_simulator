FROM ubuntu:22.04

# NPU 타겟 선택 (u55=Corstone-300/Ethos-U55, u85=Corstone-320/Ethos-U85)
# 기본은 u55 (현재 동작 검증된 경로). u85 사용 시:
#   docker build --build-arg NPU_TARGET=u85 -t fpga-simulator:u85 .
ARG NPU_TARGET=u55

# FVP 다운로드 URL (ARM Developer 직접 링크)
ARG FVP_URL_U55=https://developer.arm.com/-/cdn-downloads/permalink/FVPs-Corstone-IoT/Corstone-300/FVP_Corstone_SSE-300_11.22_35_Linux64.tgz
ARG FVP_URL_U85=https://developer.arm.com/-/cdn-downloads/permalink/FVPs-Corstone-IoT/Corstone-320/FVP_Corstone_SSE-320_11.27_25_Linux64.tgz

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/arm/gcc-arm-none-eabi/bin:${PATH}"

# 1. 시스템 의존성 및 Python 설치
# - python3 (3.10) : MLEK 빌드용 (기본값)
# - libpython3.9 : FVP 실행용 (deadsnakes PPA 사용)
RUN apt-get update && apt-get install -y \
    software-properties-common wget curl git build-essential cmake \
    xz-utils libncurses6 libdbus-1-3 libfontconfig1 libx11-6 \
    libxcursor1 libxext6 libxft2 libxi6 libxinerama1 libxrandr2 \
    libxrender1 telnet procps \
    libsndfile1 \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3 python3-pip python3-dev python3-venv \
    libpython3.9 \
    && rm -rf /var/lib/apt/lists/*

# 2. Arm GNU Toolchain (GCC 15.2) — x86_64 호스트용
WORKDIR /opt/arm
RUN wget https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-eabi.tar.xz \
    && mkdir -p gcc-arm-none-eabi \
    && tar -xJf arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-eabi.tar.xz -C gcc-arm-none-eabi --strip-components=1 \
    && rm arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-eabi.tar.xz

# 3. FVP 설치 (NPU_TARGET 에 따라 Corstone-300 또는 Corstone-320 선택)
RUN mkdir -p /opt/arm/fvp_installed \
    && case "$NPU_TARGET" in \
        u55) FVP_URL="$FVP_URL_U55" ;; \
        u85) FVP_URL="$FVP_URL_U85" ;; \
        *)   echo "ERROR: NPU_TARGET must be u55 or u85, got $NPU_TARGET" >&2; exit 1 ;; \
       esac \
    && wget -O fvp.tgz "$FVP_URL" \
    && tar -xvzf fvp.tgz \
    && INSTALL_SCRIPT=$(ls FVP_Corstone_SSE-*.sh | head -1) \
    && ./"$INSTALL_SCRIPT" --i-agree-to-the-contained-eula --no-interactive --destination /opt/arm/fvp_installed \
    && rm -f fvp.tgz FVP_Corstone_SSE-*.sh

# 설치된 FVP 실행 폴더(Linux64_GCC-9.3 등)를 표준 위치로 심볼릭 링크
RUN FVP_BIN_DIR=$(find /opt/arm/fvp_installed/models -maxdepth 1 -type d -name 'Linux64*' | head -1) \
    && [ -n "$FVP_BIN_DIR" ] || (echo "FVP install dir not found" >&2; exit 1) \
    && ln -sf "$FVP_BIN_DIR" /opt/arm/fvp_installed/bin

ENV PATH="/opt/arm/fvp_installed/bin:${PATH}"

# 빌드 시점의 NPU 타겟을 런타임에서 활용할 수 있게 보존 (sim_inside_container.sh 등이 분기 가능)
ENV NPU_TARGET=${NPU_TARGET}

# 4. Vela 설치 (기본 python3 = 3.10 환경)
RUN pip3 install ethos-u-vela

# 5. ML Evaluation Kit 설정
RUN git clone --recursive https://gitlab.arm.com/artificial-intelligence/ethos-u/ml-embedded-evaluation-kit.git \
    && cd ml-embedded-evaluation-kit \
    && python3 set_up_default_resources.py

WORKDIR /opt/arm/ml-embedded-evaluation-kit
