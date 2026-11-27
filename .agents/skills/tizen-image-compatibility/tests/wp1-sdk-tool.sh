#!/usr/bin/env bash
set -euo pipefail
base="${WP1_SR_SDK:?Set WP1_SR_SDK to the trusted SDK parent}"
tool=$(basename "$0")
if [[ "$tool" == arm-gcc ]]; then
  side="$base/vd"
else
  side="$base/llvm"
fi
host="$side/host"
loader="$host/lib64/ld-linux-x86-64.so.2"
lib="$host/usr/lib64:$host/lib64"
if [[ "$tool" == clang ]]; then
  exec "$loader" --library-path "$lib" --argv0 clang "$host/usr/bin/clang" --no-default-config --target=x86_64-linux-gnu "$@"
elif [[ "$tool" == llvm-readelf ]]; then
  exec "$loader" --library-path "$lib" --argv0 llvm-readelf "$host/usr/bin/llvm-readelf" "$@"
elif [[ "$tool" == arm-gcc ]]; then
  stem="$host/usr/bin/armv7l-tizen-linux-gnueabi-"
  cc1="$host/usr/lib/gcc/armv7l-tizen-linux-gnueabi/14.2.0/cc1"
  "$loader" --library-path "$lib" "$cc1" -quiet -fPIC -march=armv7-a -mfloat-abi=softfp -mfpu=neon -o "$3.s" "$1"
  "$loader" --library-path "$lib" "${stem}as" -march=armv7-a -mfpu=neon -o "$3.o" "$3.s"
  exec "$loader" --library-path "$lib" "${stem}ld" -shared --sysroot="$side/sysroot" --version-script="$2" -soname libwp1.so -o "$3" "$3.o"
elif [[ "$tool" == arm-clang ]]; then
  "$loader" --library-path "$lib" --argv0 clang "$host/usr/bin/clang" --no-default-config --target=armv7l-tizen-linux-gnueabi --sysroot="$side/sysroot" -march=armv7-a -mfloat-abi=softfp -mfpu=neon -fPIC -c "$1" -o "$3.o"
  exec "$loader" --library-path "$lib" --argv0 ld.lld "$host/usr/bin/lld" -shared --sysroot="$side/sysroot" --version-script="$2" -soname libwp1.so -o "$3" "$3.o"
fi
exit 2
