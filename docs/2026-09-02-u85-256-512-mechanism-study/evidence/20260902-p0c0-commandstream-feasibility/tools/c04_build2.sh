#!/bin/sh
set -e
KIT=/opt/arm/ml-embedded-evaluation-kit
W=/work/u85mech/poc
export SOURCE_DATE_EPOCH=1776763519
grep -c PER_LAYER_PROFILING $KIT/dependencies/core-driver/src/ethosu_driver.c >/dev/null || python3 /workspace/per-layer-profiling/patch-driver.py
python3 /tmp/patch_app.py
python3 /tmp/patch_device_u85.py
sha256sum $KIT/dependencies/core-driver/src/ethosu_driver.c $KIT/source/app/use_case/inference_runner/src/UseCaseHandler.cc
build_one() {
  name=$1; model=$2
  bdir=$W/build-$name
  rm -rf $bdir
  cmake -B $bdir -S $KIT \
    -DCMAKE_TOOLCHAIN_FILE=$KIT/scripts/cmake/toolchains/bare-metal-gcc.cmake \
    -DTARGET_PLATFORM=mps4 -DTARGET_SUBSYSTEM=sse-320 -DETHOS_U_NPU_ID=U85 \
    -DETHOS_U_NPU_CONFIG_ID=Z512 -DETHOS_U_NPU_MEMORY_MODE=Dedicated_Sram \
    -DETHOS_U_NPU_ENABLED=ON -DUSE_CASE_BUILD=inference_runner \
    -Dinference_runner_ACTIVATION_BUF_SZ=0x00200000 \
    -Dinference_runner_MODEL_PATH=$model > $bdir.configure.log 2>&1
  cmake --build $bdir -j $(nproc) > $bdir.build.log 2>&1
  sha256sum $bdir/bin/mlek_inference_runner.axf
}
build_one orig    /work/u85mech/artifacts/kws_micronet_m__512_Mid512/kws_micronet_m_vela.tflite
build_one control $W/kws_control.tflite
build_one irq1    $W/kws_irq1.tflite
python3 /workspace/per-layer-profiling/patch-driver.py --revert
python3 /tmp/patch_app.py --revert
python3 /tmp/patch_device_u85.py --revert
diff dependencies/core-driver/src/ethosu_device_u85.c dependencies/core-driver/src/ethosu_device_u85.c.bak.c04 > /dev/null && echo "device: reverted-identical"
cd $KIT
diff dependencies/core-driver/src/ethosu_driver.c dependencies/core-driver/src/ethosu_driver.c.bak > /dev/null && echo "driver: reverted-identical"
diff source/app/use_case/inference_runner/src/UseCaseHandler.cc source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup > /dev/null && echo "handler: reverted-identical"
echo "BUILD_PHASE_DONE"
