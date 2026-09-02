#!/bin/sh
set -e
KIT=/opt/arm/ml-embedded-evaluation-kit
W=/work/u85mech/poc
export SOURCE_DATE_EPOCH=1776763519
cd /work/u85mech
python3 /tmp/insert_irq.py artifacts/kws_micronet_m__512_Mid512/kws_micronet_m_vela.tflite poc/kws_irq3.tflite --count 3 --param 1 | tail -3
python3 /workspace/per-layer-profiling/patch-driver.py
python3 /tmp/patch_app.py
python3 /tmp/patch_device_u85.py
build_one() {
  bdir=$W/build-log-$1
  rm -rf $bdir
  cmake -B $bdir -S $KIT \
    -DCMAKE_TOOLCHAIN_FILE=$KIT/scripts/cmake/toolchains/bare-metal-gcc.cmake \
    -DTARGET_PLATFORM=mps4 -DTARGET_SUBSYSTEM=sse-320 -DETHOS_U_NPU_ID=U85 \
    -DETHOS_U_NPU_CONFIG_ID=Z512 -DETHOS_U_NPU_MEMORY_MODE=Dedicated_Sram \
    -DETHOS_U_NPU_ENABLED=ON -DUSE_CASE_BUILD=inference_runner \
    -Dinference_runner_ACTIVATION_BUF_SZ=0x00200000 \
    -DETHOSU_LOG_SEVERITY=info \
    -Dinference_runner_MODEL_PATH=$2 > $bdir.configure.log 2>&1
  cmake --build $bdir -j $(nproc) > $bdir.build.log 2>&1
  sha256sum $bdir/bin/mlek_inference_runner.axf
}
build_one orig /work/u85mech/artifacts/kws_micronet_m__512_Mid512/kws_micronet_m_vela.tflite
build_one irq1 $W/kws_irq1.tflite
build_one irq3 $W/kws_irq3.tflite
python3 /workspace/per-layer-profiling/patch-driver.py --revert
python3 /tmp/patch_app.py --revert
python3 /tmp/patch_device_u85.py --revert
cd $KIT
diff dependencies/core-driver/src/ethosu_driver.c dependencies/core-driver/src/ethosu_driver.c.bak >/dev/null && echo "driver: reverted-identical"
diff dependencies/core-driver/src/ethosu_device_u85.c dependencies/core-driver/src/ethosu_device_u85.c.bak.c04 >/dev/null && echo "device: reverted-identical"
diff source/app/use_case/inference_runner/src/UseCaseHandler.cc source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup >/dev/null && echo "handler: reverted-identical"
rm -rf $W/runlog && mkdir -p $W/runlog
for n in orig irq1 irq3; do cp $W/build-log-$n/bin/mlek_inference_runner.axf $W/runlog/$n.axf; done
python3 /tmp/c04_run.py $W/runlog || true
echo "=== verdict extraction ==="
for n in orig irq1 irq3; do
  echo "--- $n:"
  tr -d "\000" < $W/runlog/$n.uart.log | grep -E "PER-LAYER NPU PROFILING|^I: [0-9]+,|C04_OUTPUT_CRC|NPU TOTAL|inferences:" | head -10
done
echo DONE_C045
