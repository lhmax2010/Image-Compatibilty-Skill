# Historical Raspberry Pi 4 runtime observation

Earlier real-device work used an SR LLVM `tizen-headed-armv7l` Raspberry Pi 4. Four frozen probes (Clang C, Clang C++, GCC C and GCC C++) each exited 0, matched the predetermined stdout and had empty stderr. Host and deployed SHA256 matched, and the prior run observed loader and symbol-version activity and independently verified scope/process and temporary-file cleanup. These are **historical device observations**.

Two Clang results were LLVM headed native observations. The two GCC probes were observations on the same LLVM headed device. The prior work did not establish a matching VD headed native baseline or headless runtime. The formal headless matrix remained 0/8 and there were zero cross-image compatibility conclusions. The current demo uses synthetic archives and runs without a device.

See the [original headed test record](../../reviews/real-sr-runtime/HEADED_RUNTIME_RESULTS.md), [independent cleanup checks](../../reviews/real-sr-runtime/TARGET_SUPERVISOR_ADMISSION.md) and [final LLVM freeze](../../reviews/phase8k-final/FINAL_ACCEPTANCE.md).
