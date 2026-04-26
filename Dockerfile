FROM ubuntu:22.04

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

# 3. FVP Corstone-300 (x86_64 호스트용)
# 빌드 시점에 ARM Developer에서 직접 다운로드 (tarball을 image에 포함하지 않음)
RUN mkdir -p /opt/arm/fvp_installed \
    && wget -O fvp.tgz https://developer.arm.com/-/cdn-downloads/permalink/FVPs-Corstone-IoT/Corstone-300/FVP_Corstone_SSE-300_11.22_35_Linux64.tgz \
    && tar -xvzf fvp.tgz \
    && ./FVP_Corstone_SSE-300.sh --i-agree-to-the-contained-eula --no-interactive --destination /opt/arm/fvp_installed \
    && rm fvp.tgz FVP_Corstone_SSE-300.sh

# FVP 실행 파일이 들어있는 폴더를 PATH에 등록 (x86_64 호스트용)
ENV PATH="/opt/arm/fvp_installed/models/Linux64_GCC-9.3:${PATH}"

# 4. Vela 설치 (기본 python3 = 3.10 환경)
RUN pip3 install ethos-u-vela

# 5. ML Evaluation Kit 설정
RUN git clone --recursive https://gitlab.arm.com/artificial-intelligence/ethos-u/ml-embedded-evaluation-kit.git \
    && cd ml-embedded-evaluation-kit \
    && python3 set_up_default_resources.py

WORKDIR /opt/arm/ml-embedded-evaluation-kit
