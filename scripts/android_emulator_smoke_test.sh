#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-${GITHUB_WORKSPACE:-}}"
if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then
  echo "FAIL: workspace root was not passed to smoke test and GITHUB_WORKSPACE is unavailable."
  exit 2
fi
RESULTS="$ROOT/ui-test-results"
GODOT_ROOT="$ROOT/godot-source"
mkdir -p "$RESULTS"

echo "=== APK discovery ==="
APK="$ROOT/godot-editor-test.apk"
if [[ ! -s "$APK" ]]; then
  echo "Staged APK not found; falling back to a search under $GODOT_ROOT"
  APK="$(find "$GODOT_ROOT" -type f -name '*.apk' -print -quit)"
fi
if [[ -z "$APK" ]]; then
  echo "FAIL: no APK found under $GODOT_ROOT"
  echo "Files under likely output directories:"
  find "$GODOT_ROOT/bin" "$GODOT_ROOT/platform/android/java/editor/build/outputs" -maxdepth 6 -type f 2>/dev/null | head -n 300 || true
  exit 10
fi
echo "Testing APK: $APK"
printf '%s\n' "$APK" > "$RESULTS/apk-path.txt"
SDK_ROOT="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/usr/local/lib/android/sdk}}"
AAPT="$(find "$SDK_ROOT/build-tools" -type f -name aapt -print -quit 2>/dev/null || true)"
if [[ -z "$AAPT" ]]; then
  echo "FAIL: aapt not found under $SDK_ROOT/build-tools"
  find "$SDK_ROOT/build-tools" -maxdepth 2 -type f -name 'aapt*' -print 2>/dev/null || true
  exit 11
fi
echo "Using Android package tool: $AAPT"
"$AAPT" dump badging "$APK" | tee "$RESULTS/apk-badging.txt"
PACKAGE="$("$AAPT" dump badging "$APK" | sed -n "s/^package: name='\\([^']*\\)'.*/\\1/p" | head -n 1)"
if [[ -z "$PACKAGE" ]]; then
  echo "FAIL: could not read Android package name"
  exit 11
fi
echo "Package: $PACKAGE"

echo "=== Waiting for ADB device ==="
adb start-server
for attempt in $(seq 1 90); do
  STATE="$(adb get-state 2>/dev/null || true)"
  if [[ "$STATE" == "device" ]]; then break; fi
  echo "ADB state on attempt $attempt: ${STATE:-unavailable}"
  sleep 2
done
if [[ "$(adb get-state 2>/dev/null || true)" != "device" ]]; then
  adb devices -l | tee "$RESULTS/adb-devices.txt" || true
  echo "FAIL: ADB device did not become ready"
  exit 12
fi

BOOT=""
for attempt in $(seq 1 90); do
  BOOT="$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$BOOT" == "1" ]]; then break; fi
  echo "Android boot not complete (attempt $attempt)"
  sleep 2
done
if [[ "$BOOT" != "1" ]]; then
  echo "FAIL: Android system boot did not complete"
  adb logcat -d -v threadtime > "$RESULTS/boot-failure-logcat.txt" || true
  exit 13
fi
adb shell settings put system screen_off_timeout 2147483647 || true
adb shell wm size > "$RESULTS/screen-size.txt" 2>&1 || true
adb shell wm density > "$RESULTS/screen-density.txt" 2>&1 || true

echo "=== Installing APK ==="
adb install -r "$APK" 2>&1 | tee "$RESULTS/install.txt"

echo "=== Launching Godot Editor ==="
adb shell monkey -p "$PACKAGE" 1 2>&1 | tee "$RESULTS/launch.txt"
sleep 45

echo "=== Capturing UI and runtime evidence ==="
adb shell screencap -p /sdcard/godot-editor-screen.png
adb pull /sdcard/godot-editor-screen.png "$RESULTS/godot-editor-screen.png"
adb logcat -d -v threadtime > "$RESULTS/logcat.txt"
adb shell dumpsys activity activities > "$RESULTS/activities.txt" 2>&1 || true
adb shell uiautomator dump /sdcard/window.xml > "$RESULTS/uiautomator-dump.txt" 2>&1 || true
adb pull /sdcard/window.xml "$RESULTS/window.xml" || true
adb shell dumpsys meminfo "$PACKAGE" > "$RESULTS/meminfo.txt" 2>&1 || true
adb shell pidof "$PACKAGE" > "$RESULTS/pid.txt" 2>&1 || true

if [[ ! -s "$RESULTS/pid.txt" ]]; then
  echo "FAIL: Godot Editor process is not running after launch."
  tail -n 300 "$RESULTS/logcat.txt" || true
  exit 20
fi
if grep -E "FATAL EXCEPTION|Fatal signal [0-9]+|SIGSEGV|Process: $PACKAGE" "$RESULTS/logcat.txt" > "$RESULTS/fatal-errors.txt"; then
  echo "FAIL: possible fatal Android crash detected"
  cat "$RESULTS/fatal-errors.txt"
  exit 21
fi
if [[ ! -s "$RESULTS/godot-editor-screen.png" ]]; then
  echo "FAIL: screenshot is missing or empty"
  exit 22
fi
echo "PASS: APK installed; app process remained alive for 45 seconds; screenshot and runtime evidence captured."
