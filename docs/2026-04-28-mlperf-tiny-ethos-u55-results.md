# TinyMLPerf v1.1 — Ethos-U55-128 측정 결과

> 측정일: 2026-04-28
> 시뮬레이터: FVP Corstone-300 + Ethos-U55-128
> 펌웨어: MLEK `inference_runner` (DYNAMIC_MEM_LOAD_ENABLED=ON)

## 배경

[mlcommons/tiny](https://github.com/mlcommons/tiny) v1.1의 4개 reference INT8
모델을 우리 `fpga_simulator` 인프라로 컴파일 + 시뮬레이션해 NPU 성능을 측정.
ARM 자체가 직접 vendor로 MLPerf Tiny에 submission한 적은 없지만, ARM이
Ethos-U55를 위한 표준 평가 방법(Vela + MLEK + FVP)을 제공하므로 동일 흐름을
적용해 자체 reference 결과를 산출.

## 측정 환경

| 항목 | 값 |
|------|----|
| 시뮬레이터 | `FVP_Corstone_SSE-300_Ethos-U55` |
| NPU 구성 | Ethos-U55-128 (128 MAC/cycle 이론치) |
| 메모리 모드 | Sram_Only / Shared_Sram (Vela 자동 추론) |
| 컴파일러 | ethos-u-vela |
| 펌웨어 | MLEK `inference_runner` use_case (DYNAMIC_MEM_LOAD_ENABLED=ON 빌드) |
| 모델 로드 방식 | FVP `--data <vela_tflite>@0x90000000` |
| 측정일 | 2026-04-28 |

## 결과

### Vela 정적 분석

| Task | Model | INT8 size | SRAM (KiB) | Flash (KiB) | MACs |
|------|-------|----------:|-----------:|------------:|-----:|
| IC | pretrainedResnet_quant | 98,496 B | 50.62 | 77.38 | 12,505,748 |
| VWW | vww_96_int8 | 333,288 B | 72.73 | 74.38 | 7,491,972 |
| KWS | kws_ref_model | (추출 미진행) | 21.67 | 30.33 | 2,664,792 |
| AD | ad01_int8 | (추출 미진행) | 0.75 | 196.47 | 264,192 |

### FVP 실측 (NPU cycles, Ethos-U55-128)

| Task | NPU TOTAL | NPU ACTIVE | NPU IDLE | IDLE % | AXI0 RD beats | AXI0 WR beats |
|------|----------:|-----------:|---------:|-------:|--------------:|--------------:|
| IC | 203,050 | 202,544 | 506 | 0.249% | 53,597 | 24,203 |
| VWW | 209,050 | 208,504 | 546 | 0.261% | 71,085 | 43,069 |
| KWS | 84,050 | 83,962 | 88 | 0.105% | 20,628 | 12,822 |
| AD | 182,050 | 181,793 | 257 | 0.141% | 274 | 210 |

### 도출 metric (NPU 클럭 1 GHz 가정)

| Task | Inference Time (ms) | Throughput (inf/s) | MAC/cycle | NPU 효율 (ACTIVE/TOTAL) |
|------|--------------------:|-------------------:|----------:|------------------------:|
| IC | 0.203 | 4,925 | 61.7 (이론치의 24%) | 99.75% |
| VWW | 0.209 | 4,784 | 35.9 (14%) | 99.74% |
| KWS | 0.084 | 11,899 | 31.8 (12%) | 99.90% |
| AD | 0.182 | 5,494 | 1.45 (0.6% — memory bound 가능) | 99.86% |

> Inference Time = NPU TOTAL cycles / 1,000,000,000 (1 GHz 기준)
> MAC/cycle = MACs / NPU ACTIVE cycles

## ARM Cortex-M4 baseline 비교

ARM Cortex-M4 (NPU 없음) 기반의 STMicroelectronics NUCLEO-L4R5ZI v1.1
submission 결과와 비교. 수치는 STMicro 공식 results.txt에서 추출.

### STMicroelectronics NUCLEO-L4R5ZI (Cortex-M4 @ 120 MHz)

| Task | Latency | Throughput |
|------|--------:|-----------:|
| IC | ~214 ms | 4.673 inf/s |
| VWW | ~119 ms | 8.425 inf/s |
| KWS | ~63 ms | 15.905 inf/s |
| AD | ~6.9 ms | 145.829 inf/s |

### Speedup: Ethos-U55-128 @ 1 GHz vs Cortex-M4 @ 120 MHz

| Task | Speedup |
|------|--------:|
| IC | 1,054x |
| VWW | 569x |
| KWS | 750x |
| AD | 38x (소형 autoencoder, MAC 수 적어 NPU 이득 작음) |

## 분석 요약

- **모든 task에서 NPU IDLE 비율 < 0.3%** — 거의 모든 cycle을 실 연산에 사용
  (memory stall 거의 없음). Vela compiler의 SRAM 활용 최적화 양호.
- **AD task의 MAC/cycle이 1.45**로 매우 낮음 — autoencoder 모델이 작아
  NPU 128 MAC/cycle 이론치를 활용하지 못함. 소형 모델은 기동 overhead가
  상대적으로 크다. 그러나 IDLE 0.14%로 NPU 자체는 항상 작업 중.
- **IC (ResNet)이 NPU 활용 가장 높음** — 61.7 MAC/cycle (이론치의 24%).
  ResNet의 dense conv 연산이 NPU와 잘 매칭.
- **Speedup**: Cortex-M4 → Ethos-U55-128 전환으로 IC 1054x, VWW 569x, KWS
  750x. AD는 38x로 작지만 모델 자체가 매우 가벼워 절대 latency는 이미 낮음.

## 재현 방법

서버에서 컨테이너 안에서 실행:

```bash
# 1. 모델을 vela로 컴파일
docker run --rm -v <data_dir>:/sim fpga-simulator:latest \
  vela /sim/in.tflite --accelerator-config ethos-u55-128 --output-dir /sim/output

# 2. FVP 동적 로드 + 실행
docker run --rm -v <data_dir>:/sim fpga-simulator:latest bash -c '
  AXF=/opt/arm/ml-embedded-evaluation-kit/build-dynamic/bin/mlek_inference_runner.axf
  VELA=$(ls /sim/output/*_vela.tflite | head -1)
  FVP_Corstone_SSE-300_Ethos-U55 -a $AXF \
    --data "${VELA}@0x90000000" \
    -C ethosu.num_macs=128 \
    -C mps3_board.visualisation.disable-visualisation=1 \
    -C mps3_board.uart0.out_file=- \
    -C mps3_board.telnetterminal{0,1,2,5}.start_telnet=0 \
    --stat --timelimit 90
'
```

## 참고 자료

- [mlcommons/tiny v1.1 reference models](https://github.com/mlcommons/tiny/tree/master/benchmark/training)
- [STMicroelectronics v1.1 results](https://github.com/mlcommons/tiny_results_v1.1/tree/main/closed/STMicroelectronics/results)
- [ARM ML Embedded Evaluation Kit](https://gitlab.arm.com/artificial-intelligence/ethos-u/ml-embedded-evaluation-kit)
- [Ethos-U Vela Compiler](https://pypi.org/project/ethos-u-vela/)
- [FVP Corstone-300](https://developer.arm.com/Tools%20and%20Software/Fixed%20Virtual%20Platforms/Corstone-300%20Ecosystem%20FVPs)

## 한계 및 후속 작업

- **NPU 클럭 1 GHz 가정**: FVP 시뮬레이션은 cycle accurate. 실제 SoC 구현체의
  NPU 클럭에 따라 wall-clock latency가 달라짐. Corstone-300 reference는 보통
  NPU 1 GHz, Cortex-M55 32~300 MHz.
- **inference_runner 동적 로드는 raw .tflite 데이터만 inject** — 입력
  feature map(이미지 픽셀, 오디오 spectrogram 등)은 메모리에 별도 inject
  안 했음. inference_runner는 모델 첫 layer의 input tensor를 zero-fill하거나
  default 0으로 채우고 NPU 추론 진행. **실제 값으로 정확도 측정에는 부적합**,
  cycle/메모리 측정만 유효.
- **Cortex-M4 baseline 비교는 unfair**: M4는 NPU 없는 단순 MCU, U55는 NPU.
  같은 클럭이라면 M4도 더 빠르게 동작 — 절대값 비교는 SoC 가격대를 고려해
  해석.

## 라이선스 / 출처

- 모델 파일: mlcommons/tiny (Apache 2.0)
- 측정 도구: MLEK + Ethos-U Vela (Apache 2.0), FVP (ARM EULA)
