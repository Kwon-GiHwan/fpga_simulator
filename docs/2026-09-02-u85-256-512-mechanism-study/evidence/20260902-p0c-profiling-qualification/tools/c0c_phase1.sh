#!/bin/sh
# P0-C phase 1: Q-A isolation, Q-B (printf path), full-op insertion,
# clean baseline, determinism x3, Vela verbose capture.
set -e
KIT=/opt/arm/ml-embedded-evaluation-kit
W=/work/u85mech/pc
A=/work/u85mech/artifacts/kws_micronet_m__512_Mid512/kws_micronet_m_vela.tflite
export SOURCE_DATE_EPOCH=1776763519
mkdir -p $W

echo "== generate full-op instrumented model =="
python3 /tmp/insert_irq.py $A $W/kws_full.tflite --all | tail -4

cfg_build() { # $1=name $2=model
  bdir=$W/build-$1
  rm -rf $bdir
  cmake -B $bdir -S $KIT \
    -DCMAKE_TOOLCHAIN_FILE=$KIT/scripts/cmake/toolchains/bare-metal-gcc.cmake \
    -DTARGET_PLATFORM=mps4 -DTARGET_SUBSYSTEM=sse-320 -DETHOS_U_NPU_ID=U85 \
    -DETHOS_U_NPU_CONFIG_ID=Z512 -DETHOS_U_NPU_MEMORY_MODE=Dedicated_Sram \
    -DETHOS_U_NPU_ENABLED=ON -DUSE_CASE_BUILD=inference_runner \
    -Dinference_runner_ACTIVATION_BUF_SZ=0x00200000 \
    -Dinference_runner_MODEL_PATH=$2 > $bdir.configure.log 2>&1
  cmake --build $bdir -j $(nproc) > $bdir.build.log 2>&1
  sha256sum $bdir/bin/mlek_inference_runner.axf
}

echo "== B_clean: stock driver, app CRC only =="
python3 /tmp/patch_app.py
cfg_build clean $A
python3 /tmp/patch_app.py --revert

echo "== B_qa: driver v2, NO device history-clear, irq1 model =="
python3 /tmp/patch_app.py
python3 /tmp/patch_driver_u85_v2.py
cfg_build qa /work/u85mech/poc/kws_irq1.tflite
echo "== B_full_nc: driver v2, NO device clear, full model =="
cfg_build full_nc $W/kws_full.tflite
echo "== B_full_wc: + device history-clear =="
python3 /tmp/patch_device_u85.py
cfg_build full_wc $W/kws_full.tflite
python3 /tmp/patch_device_u85.py --revert
python3 /tmp/patch_driver_u85_v2.py --revert
python3 /tmp/patch_app.py --revert

cd $KIT
diff dependencies/core-driver/src/ethosu_driver.c dependencies/core-driver/src/ethosu_driver.c.bak >/dev/null && echo "driver: reverted-identical"
diff dependencies/core-driver/src/ethosu_device_u85.c dependencies/core-driver/src/ethosu_device_u85.c.bak.c04 >/dev/null && echo "device: reverted-identical"
diff source/app/use_case/inference_runner/src/UseCaseHandler.cc source/app/use_case/inference_runner/src/UseCaseHandler.cc.bak.cgroup >/dev/null && echo "handler: reverted-identical"

echo "== runtime =="
FVP=/opt/arm/fvp_installed_320/models/Linux64_GCC-9.3/FVP_Corstone_SSE-320
run_one() { # $1=tag $2=axf
  u=$W/run_$1.uart.log
  rm -f $u
  $FVP -a $2 \
    -C mps4_board.subsystem.ethosu.num_macs=512 \
    -C mps4_board.visualisation.disable-visualisation=1 \
    -C mps4_board.telnetterminal0.start_telnet=0 \
    -C mps4_board.uart0.out_file=$u \
    -C mps4_board.uart0.unbuffered_output=1 > $W/run_$1.fvp.log 2>&1 &
  FPID=$!
  ok=0
  for i in $(seq 1 90); do
    if grep -q "Total number of inferences" $u 2>/dev/null; then ok=1; break; fi
    if grep -q "Inference failed" $u 2>/dev/null; then break; fi
    sleep 2
  done
  sleep 3
  kill -9 $FPID 2>/dev/null || true
  echo "--- $1 (completed=$ok):"
  tr -d "\000" < $u | grep -E "PLPROF_BEGIN|PLPROF_END|C04_OUTPUT_CRC|NPU TOTAL|inferences:|ERROR|failed" | head -6
}
run_one clean   $W/build-clean/bin/mlek_inference_runner.axf
run_one qa      $W/build-qa/bin/mlek_inference_runner.axf
run_one full_nc $W/build-full_nc/bin/mlek_inference_runner.axf
run_one full_wc $W/build-full_wc/bin/mlek_inference_runner.axf
echo "== determinism x2 more on full_wc =="
run_one full_wc_r2 $W/build-full_wc/bin/mlek_inference_runner.axf
run_one full_wc_r3 $W/build-full_wc/bin/mlek_inference_runner.axf

echo "== vela verbose capture (kws 512@Mid_512) =="
VD=$W/vela_verbose
rm -rf $VD && mkdir -p $VD
vela --accelerator-config ethos-u85-512 --config $KIT/scripts/vela/default_vela.ini \
  --system-config Ethos_U85_SYS_DRAM_Mid_512 --memory-mode Dedicated_Sram \
  --optimise Performance --verbose-schedule --verbose-performance \
  --output-dir $VD $KIT/resources_downloaded/kws/kws_micronet_m.tflite > $VD/verbose.log 2>&1
sha256sum $VD/kws_micronet_m_vela.tflite $A | awk '{print $1}' | uniq -c
echo DONE_C0C_P1
