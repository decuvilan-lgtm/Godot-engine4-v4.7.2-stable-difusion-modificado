# Godot 4.7.2 Android Editor — ARM64 + GitHub import

## Project purpose

This repository contains the automation and patch scripts used to build a modified **Godot 4.7.2 Android Editor** from the official `godotengine/godot` source tag `4.7.2-stable`. It is not a full copy of the Godot engine source; the workflow checks out the upstream source during the build and applies our patch.

The target is Android phones using **ARM64 / `arm64-v8a` only**. Do not add `x86_64` to the phone APK. The old combined-ABI APK included both `arm64-v8a` and `x86_64`, was about 342 MB, and failed to install on the maintainer's Android 11 phone. That failure has not yet been conclusively diagnosed.

## Current modifications

### 1. GitHub project import in the Project Manager

`scripts/apply_github_import_patch.py` patches the upstream files:

- `editor/project_manager/project_manager.h`
- `editor/project_manager/project_manager.cpp`

It adds a **GitHub** button to the Project Manager. The dialog accepts a public GitHub repository URL or `owner/repository`, downloads the repository ZIP through the GitHub API, and passes the downloaded archive to Godot's project installation/import flow.

**Important:** the patch script is still part of the repository and the build workflow still runs it before compiling. The ARM64 change only changes the build target; it is not meant to remove the GitHub import feature. The patcher intentionally checks each source anchor and fails if an expected anchor is missing or appears more than once.

### 2. ARM64-only Android build

Workflow: [`.github/workflows/build-godot-android-source.yml`](.github/workflows/build-godot-android-source.yml)

The manual workflow:

1. Checks out this repository and official Godot source at `4.7.2-stable`.
2. Applies `scripts/apply_github_import_patch.py`.
3. Sets up Java 17, Python 3.12, and SCons.
4. Installs the Android Swappy dependency.
5. Compiles the editor engine with `arch=arm64` only.
6. Generates the Android editor APK with Gradle.
7. Checks the APK contents and requires the native ABI list to be exactly `arm64-v8a`.
8. Checks ZIP integrity, verifies the APK signature, checks ZIP alignment, and prints the SHA-256.
9. Uploads the artifact named `godot-4.7.2-android-editor-arm64-only`.

The intended APK filename in the artifact is `godot-editor-arm64.apk`; `apk-badging.txt` is included as build evidence.

### 3. Validation workflow

The manual workflow has two options:

- `full-android-build`: build and validate the ARM64-only APK.
- `validate-import-only`: check the patcher's Python syntax and apply the patch against a fresh upstream checkout.

Run it from GitHub: **Actions → Build Godot Android Editor (source pipeline) → Run workflow**.

## Current state and known gaps

- The previous combined ARM64 + x86_64 build successfully installed and launched in an x86_64 Android emulator, but that does **not** prove it will install on every ARM64 phone.
- The latest workflow change removes x86_64 from compilation and APK packaging.
- Because the hosted test emulator was x86_64, the latest workflow no longer runs that emulator install/launch test or uploads its UI screenshots. Do not claim the new ARM64 APK passed a device install test until an ARM64-compatible test device/emulator has actually been used.
- The new APK build and its ABI/signature/alignment checks have not been confirmed successful yet. Check the newest GitHub Actions run and its artifact before sharing an APK.
- An ARM64-only APK will not install on Android systems that expose only a 32-bit ARM ABI. If installation fails again, collect the exact device ABI list and Android Package Installer/ADB error rather than assuming the architecture is the only cause.

## Next steps

1. Run `full-android-build` and inspect the complete log.
2. Confirm `aapt dump badging` reports only `arm64-v8a`, and confirm the signature, alignment, and ZIP checks pass.
3. Download only the artifact named `godot-4.7.2-android-editor-arm64-only`.
4. Test installation on an actual ARM64 Android device. If it fails, capture the precise installer error or run `adb install -r godot-editor-arm64.apk` and record the returned error.
5. Restore automated launch/screenshot coverage using an ARM64-compatible test environment if available; do not reintroduce x86_64 into the phone APK merely to reuse an x86_64 emulator.

## Rules for future contributors and AI assistants

- Read this README and the current workflow before editing anything.
- Preserve `scripts/apply_github_import_patch.py` and its invocation in the build workflow unless explicitly asked to remove GitHub import.
- Keep the Android deliverable `arm64-v8a` only. Do not build `x86_64` into the APK.
- Make changes narrowly and inspect the commit diff to ensure unrelated patches and features were not removed.
- Never state that a build, signature check, installation, or runtime test succeeded unless a corresponding current workflow log or device result proves it.
- Treat upstream Godot source as a temporary build checkout. Make durable customizations in this repository's scripts/workflow, or deliberately maintain a patch file, so changes are reproducible.
