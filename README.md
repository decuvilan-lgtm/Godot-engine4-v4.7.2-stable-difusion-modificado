# Godot 4.7.2 Android Editor — GitHub import (ARM64)

## Actual objective

Keep the existing **Godot Android editor** and make the smallest targeted change needed to let the Project Manager import a project from a public GitHub repository. Do not redesign or recreate Godot, and do not replace its Android editor with a different application.

An APK is a compiled package, so the maintainable way to add a native Project Manager button is to patch the corresponding Godot source and rebuild the Android APK. The workflow must build and publish the **complete Android editor APK**, not a small Gradle intermediate.

## Repository layout and source of truth

This repository currently stores:
- `.github/workflows/build-godot-android-source.yml` — reproducible build and validation workflow.
- `scripts/apply_github_import_patch.py` — minimal source patch for GitHub import.
- `README.md` — project notes and test history.

The Godot engine source is checked out by the workflow from `godotengine/godot`, tag `4.7.2-stable`, into a temporary `godot-source` directory. It is not committed as a full engine source tree in this repository, and the generated APK is stored as a GitHub Actions artifact rather than committed to the repository.

## Intended source modification

`scripts/apply_github_import_patch.py` patches only:
- `editor/project_manager/project_manager.h`
- `editor/project_manager/project_manager.cpp`

It adds a **GitHub** button to the existing Project Manager. The dialog accepts a public GitHub repository URL or `owner/repository`, downloads the repository ZIP via GitHub's API, and passes it to Godot's existing project install/import flow.

This is public-repository import only; private repositories and authenticated GitHub access are not implemented. The patcher checks source anchors and fails if the expected upstream code has changed.

## Android build workflow

Workflow: [Build Godot Android Editor](.github/workflows/build-godot-android-source.yml)

The `full-android-build` job:
1. Checks out the repository and official Godot 4.7.2 source.
2. Applies the GitHub import patch.
3. Sets up Java 17, Python, SCons and the Android Swappy dependency.
4. Compiles the Android editor native engine for `arm64` only, with `generate_android_binaries=yes` so SCons emits the native editor binaries required by the APK.
5. Runs Gradle's `generateGodotEditor` task without `clean`, preserving the binaries produced by SCons.
6. Packages the editor APK from Godot's documented output location: `godot-source/bin/android_editor_builds/android_editor-android-debug.apk`.
7. Refuses to publish the APK if the expected full-editor APK is missing or smaller than 50 MB. This guard exists because run 29 accidentally staged a roughly 13 MB APK from a Gradle intermediate output directory.
8. Verifies ZIP integrity, checks `aapt dump badging` reports exactly `arm64-v8a`, verifies APK signature and ZIP alignment, and records SHA-256.
9. Uploads `godot-editor-arm64.apk` and `apk-badging.txt` as the `godot-4.7.2-android-editor-arm64-only` artifact.

The separate `validate-import-only` option checks the patcher's Python syntax and applies it to a clean upstream source checkout. It does not build an APK or test the runtime UI.

## Test history (2026-10-22)

### Run 28 — [39703513753](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39703513753)

- Build completed successfully.
- APK was approximately 342 MB and included both `arm64-v8a` and `x86_64`.
- The Android x86_64 emulator successfully installed and launched this APK; UI-test evidence was uploaded.
- This proves the prior dual-ABI package launched in that emulator, **not** that it installs on the user's ARM64 Android 11 phone.
- The user's earlier phone install failure remains undiagnosed.

### Run 29 — [39715595661](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39715595661)

- Build, ZIP integrity, signature, alignment, and ARM64-only ABI checks all reported success.
- The APK identified by the workflow was only about 13 MB (SHA-256: `f0fdd52895f1b12b952b45c003a224e8a245f97f9a980da9f448edfe66320d2d`).
- It was taken from `platform/android/java/editor/build/outputs/apk/android/debug/`, which is not the documented complete-editor output location. Therefore run 29 does **not** establish that a complete editor APK was packaged, installed, or launched.
- Artifact ZIP size was about 8.9 MB; that small artifact was not proof of a complete editor package.
- No ARM64 device/emulator installation test was run in run 29.

### Run 30 — [39719700905](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39719700905)

- SCons compilation and Gradle `generateGodotEditor` both completed successfully, but the expected output APK was only 12,823,634 bytes (about 12.8 MB).
- The size guard correctly refused to publish it; no artifact was created. This is not a successful deliverable.
- Comparing the workflow with the official Godot Android build documentation exposed a missing `generate_android_binaries=yes` flag in the SCons editor build. The workflow also ran Gradle `clean` immediately before `generateGodotEditor`, unlike the official Godot workflow.

### Current corrective change

Commit `894b99d89c5659f00a6b0a64a4b52517c5c6166e` adds `generate_android_binaries=yes` and removes Gradle `clean` before generating the editor. The workflow still selects `godot-source/bin/android_editor_builds/android_editor-android-debug.apk` and refuses to publish if it is missing or smaller than 50 MB. This correction has **not yet been validated by a new run**; inspect the next run and actual APK artifact before claiming success.

## Known scope and next verification

- The target APK is ARM64 / `arm64-v8a` only; do not add `x86_64` to the phone APK just to reuse an x86_64 emulator.
- The GitHub import feature currently supports public repositories only.
- Build success and static APK checks do not prove the GitHub button works at runtime.
- After the corrected build, verify the artifact contains the complete editor APK, install it on an ARM64 Android device, open Project Manager, test a public repository import, and record the exact result. If install fails, capture the Android installer error or `adb install` output.

## Rules for future changes

- Read this README and the workflow before editing.
- Preserve the Android editor and keep the GitHub import patch narrow.
- Do not claim an install, launch, or GitHub-import test passed without a corresponding log or device result.
- Keep durable source changes in the patch script/workflow so builds are reproducible; do not treat editing the APK ZIP directly as a substitute for modifying source and rebuilding.
