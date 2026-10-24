# Godot 4.7.2 Android Editor — GitHub import (ARM32 + ARM64)

## Current continuation status — 2026-10-24

### Important correction: GitHub import/search was already working

**The project owner confirms that the GitHub functionality had already worked. Do not describe GitHub as a broken feature or imply that the recent URL-normalization work made the core Git integration work for the first time.** The existing GitHub import/search flow is established functionality; the latest edits are narrow follow-up improvements to the explicit search fallback and to handling browser-copied URLs (such as `www.github.com`, repository subpages like `/tree/main`, and query/fragment metadata).

The recent fallback edits are **not yet rebuilt or verified on-device**, so they must not be presented as a verified improvement. Keep that distinction clear:
- **Existing GitHub functionality:** previously working according to the project owner.
- **Recent search-fallback URL handling changes:** source-only; Android behavior not yet confirmed.
- **Full APK/device status:** use the dated build history below; do not infer a current APK from source commits alone.

### Performance requirement clarified by the project owner

**The goal is a smoother, more responsive editor and game preview—not reducing features, disabling capabilities, arbitrarily limiting background work, or lowering quality as a blanket fix.** The user specifically reports that running the game preview itself can lag on the LG K51 / Android 11.

Performance work must therefore be measurement-led:
- Profile frame time and frame pacing while the editor is idle, while editing a scene, and while the game preview is running.
- Separate editor UI/input latency from game-rendering time, import/shader-compilation stutters, and CPU/GPU contention between the editor and preview.
- Reproduce the issue on the target Android device before changing renderer, scheduling, cache, quality, or feature behavior.
- Prefer fixing unnecessary work, repeated redraws, stalls, synchronization, or expensive paths while retaining features and intended visual quality.
- Do not call the editor “optimized” until comparable before/after measurements show an improvement and the same preview features still work.

### Preview/run-bar debug visibility menu — source added, not yet validated

- Added a **Debug** menu directly to Godot's existing run bar, alongside the play/pause/stop controls, so the common runtime overlays are reachable without opening the Debug menu or adding temporary scripts.
- Options: **Visible Collision Shapes** (2D/3D collision shapes and raycasts), **Visible Paths**, **Visible Navigation**, **Visible Avoidance**, and **Debug CanvasItem Redraws**.
- Every option defaults to **off** for a new project. Existing per-project preferences are respected. The menu writes Godot's existing `debug_options` project metadata, which the run launcher already reads.
- **All five controls now have source-level live-toggle wiring** through the editor's remote-debugger channel. Collision Shapes calls Godot's live physics-server debug switch; Navigation and Avoidance send runtime commands to the navigation servers; CanvasItem Redraws calls `RenderingServer::canvas_item_set_debug_redraw`; and Visible Paths now explicitly refreshes the built-in `Path2D` renderer and creates/updates/hides the `Path3D` debug instance when toggled. Godot documents the `SceneTree` path hint itself as not designed for runtime changes, so the patch does not rely on that hint alone. These C++ changes are not yet compiled or runtime-verified.
- This is a source patch only. It has not been applied to a fresh Godot checkout, compiled, or checked on the LG K51. Do not treat the menu as verified until the source patch and Android UI are validated.

### Latest overlay validation status — 2026-10-24

- **PASS — [Windows source validation run 40060330082](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40060330082):** Python syntax and overlay checks passed, and the patcher applied successfully to a clean, sparse checkout of official Godot 4.7.2 source.
- **IN PROGRESS — [Windows Android native compile run 40060228767](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40060228767):** targeted only the ARM64 Android editor native engine and was superseded by the ARM32-first workflow. It does **not** run Gradle or generate/package an APK. C++ compile status is not confirmed yet.
- The source-validation path exposed and corrected an upstream-anchor mismatch: official Godot 4.7.2 does not already declare the collision remote-debugger functions assumed by the earlier patch. The patch now adds the collision message end-to-end instead of relying on nonexistent declarations.
- Windows runner setup issues were addressed: long Git paths are enabled for the full source checkout, and the obsolete Android SDK `tools` package is no longer requested.
- The Linux-based MCP addon workflow is now manual-dispatch only. Overlay source checks and the compile-only check use Windows runners; do not run Linux tests or build/package a full APK without a separate explicit request.

### Missing editor controls — current implementation step

- Extended `inspect_editor_ui` to enumerate open Godot `PopupMenu` controls and expose each item’s label/index, disabled/separator state, and checked state. `activate_editor_ui_control` now accepts a desired `checked_value` for checkable menu entries, avoids toggling when the requested state is already active, and verifies the resulting state. This is groundwork for operating built-in debug menu options (including collision visualization) without temporary scripts.
- Extended the packaging script’s static guard so the popup-menu inspection behavior cannot silently disappear from the generated addon.
- This does **not** mean all editor functions or collision/debug overlays are finished. The change remains source-only; parser/runtime and Android checks are pending. Next: inspect the actual Android editor menu surface and add dedicated typed actions where the generic UI bridge cannot reach an option reliably.

### Android Gallery pollution fix — source-only

- ZIP-based project installs now create a root-level `.nomedia` marker **before extracting project assets**, so Android's media scanner should skip image/audio descendants instead of flooding the Gallery with game assets.
- The patch preserves an existing repository-provided `.nomedia` file and aborts the install before extraction if it cannot establish the marker. This is aimed at project assets, not photos the user explicitly saves elsewhere.
- **Not yet compiled or tested on the phone.** It should prevent future imports from being indexed; media already indexed from a previous import may remain visible until Android refreshes its media database. The assistant cannot remove those entries from the user's device remotely.

### Source changes in this continuation

- **GitHub behavior:** core import/search already worked before the latest follow-up. The explicit **“Buscar en GitHub”** handler and URL normalization are refinements, not the original implementation or proof of a newly fixed core feature.
- **Gallery behavior:** the source patch now adds `.nomedia` to ZIP-installed projects before extraction to keep project assets out of Android Gallery; it is source-only until rebuilt and checked on-device.
- **Workflow safety:** workflows are configured for manual dispatch only to avoid automatically launching Linux-runner checks on source edits. Do not launch Linux tests/builds; the owner explicitly asked not to run tests on Linux.
- **Not yet verified:** the latest fallback C++ patch has not been applied to a fresh Godot source checkout, compiled, packaged into a new APK, or exercised on the LG K51. Preview smoothness has not yet been measured or improved; no rendering quality or editor feature has been deliberately removed.



### Continuity log — 2026-10-23 (current working order)

This entry supersedes older “next step” notes below whenever they conflict with the current priorities.

1. **Preserve the distinction between existing GitHub functionality and follow-up changes.** The project owner confirms GitHub import/search already worked. Recent source-only edits refine the explicit search fallback for copied URLs, including `www.github.com`, repository subpages such as `/tree/branch`, and query/fragment metadata. Direct URL import remains a separate path. These refinements have not been compiled or tested on Android; review URL encoding, result selection, pagination, ZIP download, and error handling without describing the original GitHub feature as broken.
2. **Keep the native C++ patch unclaimed until compiled.** The new fallback handler is source-only. Do not describe it as working on Android until a complete editor APK containing the change is built and the UI is exercised.
3. **Do not run Linux tests or automatically launch Linux CI.** The Android build workflow remains manual-dispatch only. No new Linux test/build was started for this continuation.
4. **Treat preview lag as a separate performance task.** The user reports lag in the running-game preview on the LG K51 / Android 11. First obtain comparable on-device frame-time/frame-pacing evidence and determine whether the bottleneck is the editor, the game renderer, import/shader work, or resource contention. Do not “fix” this by stripping features, imposing arbitrary resource caps, or lowering visual quality.
5. **Do not merge PR #1 or offer a new APK as verified** until its actual build/package status and required device behavior have been checked.

**Current evidence:** the README and source patch changes are committed on `feature/github-sync-and-safe-mcp`; no new APK, Android-device test, or measured preview-performance improvement is established by this log. Keep source changes, automated checks, APK packaging, and physical-device results recorded as separate evidence categories.

## Current verified status — 2026-10-22 (supersedes older “not yet tested” notes below)

Work branch: `feature/github-sync-and-safe-mcp`  
Feature-source commit validated by CI: `9731955a628fee0d38fee7ef8237c40549245853`. Latest documentation commit: `9754a37f9f25edff9acf63409b2cc5484a7f28ae`.

### Latest automated validation

- **PASS — [MCP addon validation run 116](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39850311591).** Python syntax validation, application of the Project Manager patches to a clean Godot 4.7.2 source checkout, addon packaging, headless Godot parser/load, archive-content checks, and checks that the Android APK workflow embeds the hardened addon all passed.
- The run exposed stale test assertions during earlier attempts; those assertions were updated to match the safer `PopupMenu` activation and escaped C++ source text. The successful run above is the current result.
- **CANCELLED — [Android build run 66](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39846632240).** The README push interrupted native compilation before APK generation; this run did not produce a verified APK.
- **IN PROGRESS — [Android build run 67](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39850311596).** This replacement build targets both ARM32 (`armeabi-v7a`) and ARM64 (`arm64-v8a`). Its addon packaging passed, but compilation/artifact verification has not yet been confirmed complete.
- Validation run 115 also passed; run 116 is the latest completed validation and passed after the README status update triggered a fresh workflow.
- Older build run 65 was cancelled by a later push. A cancelled run is neither a successful build nor proof of an APK defect.

### What is and is not proven

**Proven in CI:** source patch applies to the selected Godot 4.7.2 source; addon package can be generated; Godot headless can parse/load the generated addon; static archive/workflow safety checks pass; build run 67 has passed addon packaging and is the current Android build.

**Not yet proven:** build run 67 finishes compiling; a full editor APK is generated and verified to contain both ABIs; installation and launch on the user's LG K51 running Android 11; GitHub import button behavior on-device (default branch, explicit branch/tag/commit, pagination and failures); or end-to-end MCP operation against a real editor/game. No current APK download link should be offered until the build succeeds and the uploaded artifact is checked.

The original GitHub functionality was already working according to the project owner. The current priority is to avoid regressing it, verify the recent fallback refinements when an approved non-Linux/device workflow is available, and establish the correct current ARM32+ARM64 APK/device status before merging. A green addon validation is not a substitute for an APK build or a physical-device test.

---


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
4. Compiles the Android editor native engine for both `arm32` (`armeabi-v7a`) and `arm64` (`arm64-v8a`), passing `generate_android_binaries=yes` to the final architecture build so Godot packages both native ABIs.
5. Runs Gradle's `generateGodotEditor` task without `clean`, preserving the binaries produced by SCons.
6. Packages the editor APK from Godot's documented output location: `godot-source/bin/android_editor_builds/android_editor-android-debug.apk`.
7. Refuses to publish the APK if the expected full-editor APK is missing or smaller than 50 MB. This guard exists because run 29 accidentally staged a roughly 13 MB APK from a Gradle intermediate output directory.
8. Verifies ZIP integrity, checks `aapt dump badging` reports exactly both `armeabi-v7a` and `arm64-v8a`, verifies APK signature and ZIP alignment, and records SHA-256.
9. Uploads the combined `godot-editor-arm32-arm64.apk` and `apk-badging.txt` as the `godot-4.7.2-android-editor-arm32-arm64` artifact.

The separate `validate-import-only` option checks the patcher's Python syntax and applies it to a clean upstream source checkout. It does not build an APK or test the runtime UI.

## Latest automated integration result

### Run 32 — [39772776142](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39772776142)

- **Result: success** (completed 2026-10-22 at 12:17:45 UTC).
- Both `build-android-editor` and `package-safe-mcp-addon` jobs completed successfully.
- Native Android editor compilation and Gradle APK generation succeeded.
- The APK is approximately 172 MiB; SHA-256: `3ff89bd47287e01a8801c8ffa3f5228b6e176681bb4d35afccb1352e8a34db68`.
- APK checks passed: ZIP integrity, signature verification, ZIP alignment, and the exact `arm64-v8a` native ABI check.
- The final APK contains `assets/mcp-addon/plugin.cfg`, the MCP tool registry and server scripts. Static checks found the expected loopback binding and rejected the generic script executor, project deletion marker and wildcard CORS.
- The source patch containing the GitHub import and **Install MCP** Project Manager code was applied before compilation; the C++ build succeeded.
- **Not yet proven:** Android installation on the user's phone, actual Project Manager button visibility/interaction, copying from APK assets into a real project, plugin activation/parser success, MCP client round-trip, or runtime undo/redo behavior. CI's APK content checks are static, not an on-device end-to-end test.

Artifact: [`godot-4.7.2-android-editor-arm64-only`](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39772776142) (available until 2026-11-21).

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

### Run 31 — [39722571162](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39722571162)

- Build completed and published artifact `godot-4.7.2-android-editor-arm64-only` (artifact ID `12403042462`, approximately 84 MiB as a ZIP).
- The APK inside is 179,432,685 bytes (about 171 MiB), SHA-256 `896f1c34e6501872ee8ce038826981fd579f2535950ea2437e3c93c79b16592e`.
- Metadata reports package `org.godotengine.editor.v4.debug`, version `4.7.2.stable`, min SDK 24, and native code exactly `arm64-v8a`. ZIP integrity, v2 signature verification, and ZIP alignment passed.
- This run verifies a complete-sized ARM64-only build artifact and static package checks. It does **not** prove installation on the user's LG K51 / Android 11 phone, runtime behavior of the GitHub button, or MCP integration. The phone's install failure remains unresolved.

### Current corrective change

Commit `894b99d89c5659f00a6b0a64a4b52517c5c6166e` adds `generate_android_binaries=yes` and removes Gradle `clean` before generating the editor. The workflow still selects `godot-source/bin/android_editor_builds/android_editor-android-debug.apk` and refuses to publish if it is missing or smaller than 50 MB. Run 31 subsequently validated this correction at the build/artifact level: the full-sized ARM64-only APK was produced and passed static package checks. This still does not establish installation or runtime behavior on the user's physical phone.

## Planned feature: multi-repository GitHub synchronization

**Status: design documented; not implemented yet.** The current GitHub button only imports a public repository ZIP. It does not yet provide the synchronization system described below.

### User-facing workflow

- Provide one main **Synchronize** entry point in both the Project Manager and the editor.
- The entry point lists connected GitHub accounts and their accessible repositories, grouped by account (for example, `gavilandavid/pril`, `gavilandavid/prop-hunt`, and repositories under a second account).
- Each repository has its own **Analyze** and **Synchronize** actions.
- The user chooses a separate local project folder for every repository. Two different repositories must not silently share or overwrite the same destination.
- Each repository also has its own rescue folder, located outside both the project directory and the repository. Rescue files are local-only: they are never uploaded to GitHub and are not shown as project files in Godot.
- Synchronization is manual only. No background polling, automatic sync, or automatic upload from Godot to GitHub.
- GitHub is the remote source of truth for synchronized files. The intended flow is **ChatGPT/developer changes → GitHub → manual sync → local project → Godot**.

### Analyze: incremental by default

Analyze should not rescan or download the entire repository on every run.

- Store a per-repository baseline after the first successful sync: repository identity, selected branch, last successfully applied commit SHA, tracked paths, and file hashes or equivalent reliable metadata.
- Ask GitHub for changes between the baseline commit and the current branch commit. Build the pending change set from that comparison.
- Compare local files against the saved baseline, concentrating hash checks on affected paths and relevant directories.
- Detect additions, modifications, deletions, renames, and moves. GitHub can report likely renames on the remote side; local rename/move detection must compare the previous path/hash manifest with current local paths and hashes.
- Prepare a reusable plan containing old and new paths, remote downloads, local rescue operations, deletions, conflicts, and the exact remote commit SHA analyzed.
- Analyze must not change project files or move files to rescue. Only Synchronize applies the plan.
- If the remote branch advances after analysis, refresh/revalidate the plan before applying it. If the baseline is missing or inconsistent, perform a controlled recovery scan rather than blindly applying a stale plan.
- If there are no pending changes, report that the project is already synchronized.

### Synchronize: safe, incremental, and one-way

- First sync: download and install the full repository contents, then write the baseline only after validation succeeds.
- Later syncs: download only newly added or modified file contents required by the change set. Do not download a full ZIP for every sync.
- Apply remote deletions, renames, and moves to restore the remote directory structure.
- Before replacing, moving, or removing a local file that differs from the saved baseline, automatically copy/move its local version into the repository's separate rescue area. Rescue must use collision-safe unique names so an earlier rescue is never overwritten.
- Local-only files are moved to rescue, not uploaded. Locally renamed/moved files are rescued and the official remote paths are restored.
- A local file deleted by the user is restored if it still exists remotely.
- Files deleted remotely are removed locally only after any uncommitted local content has been rescued.
- If a rename/move cannot be identified confidently, protect the local file and record the ambiguity rather than guessing destructively.
- Exclude known generated/cache paths such as Godot's `.godot/` from ordinary project-change handling where appropriate; define exclusions carefully so real source assets are not skipped.
- Use a staging area and validate downloads before applying changes. Failed downloads or invalid archives must not modify the working project.
- Update the baseline commit and manifest only after the entire sync has completed successfully. A partial failure must be recoverable and must not advance the baseline prematurely.
- Never push, commit, or upload local project/rescue changes to GitHub automatically.

### Performance and scale goals

The synchronizer should handle large change sets without treating each file as a separate sync operation. Example workload for testing (not a hard limit): 40 renames, 50 moves, 70 deletions, and 20 new files in one update.

- Batch API metadata requests where possible and obey GitHub rate limits.
- Use hashes and the saved manifest to avoid re-reading or re-downloading unchanged content.
- Bound parallel downloads to avoid overwhelming the phone or network.
- Apply file operations in a planned order, accounting for directory moves, path collisions, case sensitivity, and rename cycles.
- Show a summary of the pending operations and any ambiguous cases before applying the plan. Routine rescue is automatic once sync begins; users should not need to approve every rescued file individually.
- Measure performance on actual Android devices before promising specific speed.

### Accounts, permissions, and local storage

- Public repositories can be accessed without login, but listing a user's repositories and accessing private repositories requires GitHub authentication and appropriately scoped permissions.
- Store credentials securely; never put access tokens in project files, rescue folders, logs, or the repository.
- Support multiple connected accounts and keep each account/repository configuration isolated.
- Android storage permissions and scoped-storage behavior must be verified. Let users select writable local destinations and rescue locations; do not assume every arbitrary device folder is accessible.
- Repository identity, branch, destination path, rescue path, and manifest must be stored independently for each configured repository.

## Android ABI support: ARM32 and ARM64

**Required target:** one combined Android editor APK that supports both `armeabi-v7a` (ARM32) for older/32-bit devices and `arm64-v8a` (ARM64) for newer devices.

- The earlier workflow and Run 40 artifact were ARM64-only and did not meet this requirement.
- The build workflow has now been changed to compile the Android editor for `arm32` first and `arm64` second, then generate the combined APK from both architecture builds.
- The updated validation requires the APK's native ABI metadata to contain exactly both `armeabi-v7a` and `arm64-v8a`; an ARM64-only artifact must fail validation.
- **Pending verification:** the new workflow run must complete, the APK must pass ABI/signature/integrity checks, and installation/launch must be tested on real devices. Do not call the dual-ABI build successful until those checks pass.
- Keep both ABIs enabled in future builds. Do not silently revert to ARM64-only packaging.

## Known scope and next verification

- The current target APK is ARM64 / `arm64-v8a` only; ARM32 support remains a goal requiring research and validation.
- The current GitHub button supports public repository import only; multi-account browsing, authentication, Analyze, incremental synchronization, and rescue handling are future work.
- Build success and static APK checks do not prove that the APK installs or that the GitHub button works at runtime.
- After the corrected build, verify the artifact contains the complete editor APK, install it on a compatible Android device, open Project Manager, test a public repository import, and record the exact result. If install fails, capture the Android installer error or `adb install` output.

## Rules for future changes

- Read this README and the workflow before editing.
- Preserve the Android editor and keep the GitHub import patch narrow.
- Do not claim an install, launch, or GitHub-import test passed without a corresponding log or device result.
- Keep durable source changes in the patch script/workflow so builds are reproducible; do not treat editing the APK ZIP directly as a substitute for modifying source and rebuilding.

## Confirmed implementation decisions: GitHub sync and Android MCP

The active implementation branch is `feature/github-sync-and-safe-mcp`.

### GitHub sync scope
- Accept **public repositories only**. Do not implement GitHub OAuth, private repository browsing, token storage, or private repository access.
- Keep the sync action manual and one-way: GitHub to local project.
- Keep Analyze read-only and bind its plan to the exact remote commit SHA.
- Rescue local-only or locally modified files outside the project before overwriting/removing them. Never upload rescue content.
- Keep each repository's destination, manifest, baseline, and rescue folder isolated.

### Android MCP scope and safety
- Build on the Android-compatible GDScript editor plugin, then expand its tool registry in parallel with GitHub sync.
- Goal: broad editor operations covering project inspection, scenes, nodes, scripts, properties, resources, filesystem, runtime testing, and diagnostics.
- **Hard prohibition: no MCP tool may delete a Godot project or its project directory.** Do not expose a `delete_project` tool. Any generic script/evaluation facility must not be allowed to bypass this rule.
- Keep destructive operations behind explicit safeguards and prefer Godot's undoable editor APIs where available.
- MCP listeners must remain loopback-only by default. Do not expose unauthenticated editor control on a LAN or public interface; any remote bridge needs authentication and a separate security review.
- Do not claim ChatGPT is connected to the live editor until an actual supported client connection has been configured and tested. Adding an addon to the repository alone does not establish that connection.

### Parallel work and verification
- Sync and MCP work are independent tracks; neither should block progress on the other.
- Keep the existing Android APK build path intact while changing the patcher or packaging.
- Verify source changes with automated checks before attempting a full APK build. A successful build or artifact upload is not proof of installation or runtime behavior on the user's phone.

### MCP coverage requirement: full editor surface, including obscure panels

The MCP goal is not a short list of convenience tools. Aim for broad, systematic coverage of the Godot editor UI and APIs, including obscure, advanced, infrequently used, and seemingly unnecessary sections and options.

Coverage should include:
- Editor main menus, submenus, contextual/right-click menus, toolbar buttons, docks, inspectors, bottom panels, dialogs, popups, project settings, editor settings, export settings, import/resource settings, and relevant keyboard commands.
- Scene tree and scene editing, node creation and configuration, all applicable inspector properties, scripts and resources, filesystem and resource import, animation, tilemaps, shaders, materials, audio, physics, navigation, debugging, profiling, running/stopping/testing, output/errors, plugins, and project configuration.
- Read-only inspection of editor state plus typed actions that operate through supported Godot editor APIs where possible.
- A coverage inventory mapping each visible editor section/action to an MCP capability, with explicit statuses for implemented, partially implemented, unavailable, or unsafe.
- A discoverable generic UI/action layer where feasible, so unusual controls are not omitted simply because they do not have a dedicated named tool. Prefer stable APIs and accessible control metadata over brittle screen-coordinate clicking.
- Preserve an absolute project-deletion prohibition: no tool may delete the project, its project root, or recursively remove the project directory. Generic script/evaluation tools must not bypass this policy. File/node edits that can destroy work require guardrails, and should use undoable editor operations where available.

Do not claim literal 100% coverage until an automated inventory and device-side tests verify it. The goal is to expose the broadest feasible set of editor options and report honest gaps. This is an editor plugin and a tool server, not proof that ChatGPT can connect directly to the live editor; the actual client/transport connection must be configured and tested separately.

## Current MCP-to-APK integration status (checked 2026-10-22)

**Integration is in progress; not yet verified by a new APK build.** The build workflow has now been changed to check out the pinned MCP source, run the hardening/package script, copy the hardened addon files into Android editor assets at `assets/mcp-addon/`, and assert that key addon files and safety properties are present in the final APK. This change has not yet passed a new full Android build, so do not claim the APK contains them until a workflow run confirms it. The separate `godot-mcp-android-safe.zip` artifact remains available for testing.

The reason this needs a deliberate design is that the upstream MCP code is a Godot `EditorPlugin`: Godot normally enables editor plugins per project. Merely copying the addon ZIP into the APK, or placing it somewhere inside the APK, would not make it available and active in every project. Do not call that integration.

### Verified safeguards in the separately packaged addon

- Upstream is pinned to `GeorgeMee/godot-mcp-android` commit `5df91076250ece38ab182b2ca8b8a4a5d9a2d938`.
- The packaging script removes the generic `execute_script` tool and its implementation; it asserts that no `delete_project` tool is registered.
- HTTP and WebSocket listeners are patched to bind to `127.0.0.1`; wildcard HTTP CORS is removed.
- Scene property changes and node removal are patched to use the editor undo/redo manager.
- Workflow run [39737203890](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39737203890) passed static packaging checks and produced artifact `godot-mcp-android-safe` (artifact ID `12407299346`).

These are source/package checks only. They do not yet prove that Godot parses the addon, undo/redo works in a live editor, a compatible MCP client can connect, or that the feature works on Android.

### Latest implementation step — embed the addon payload

Commit `e0910b96537b3b04093bdf01c38ddded440e157d` updates `.github/workflows/build-godot-android-source.yml` to stage the hardened addon under the Android editor module's `src/main/assets/mcp-addon/` before Gradle packages the APK. The APK validation step now checks for the embedded `plugin.cfg` and tool registry, rejects generic script execution/project-deletion markers in the registry, verifies loopback bindings, and rejects wildcard CORS.

**Status: code committed; build/runtime validation pending.** The added static workflow guard passed in [validation run 30](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39771939321) and [validation run 29](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39771932750). Those runs confirm that the workflow contains the pinned source, asset-staging step, and final-APK assertions; they do **not** run the Android build or prove the assets are in a generated APK. Earlier runs 27–28 exposed a quoting error in the new static test, which was corrected and then passed. This is the first physical-embedding step, not the completed user-facing integration. The addon still needs a safe Project Manager/editor install flow that copies it into a chosen project and enables it only with user confirmation. The build must also confirm Android's Gradle packaging preserves the asset paths as expected.

### Next implementation step — Project Manager installer

Commit `c3bfe45acd0a9d3c9567c61cca5befbd3a7b230b` extends `scripts/apply_github_import_patch.py` with an **Install MCP** Project Manager button. The intended flow requires exactly one selected, existing Godot project, asks for confirmation, refuses to overwrite an existing `addons/godot_mcp_android` folder, copies the bundled addon into the project, and adds the plugin path to `[editor_plugins].enabled` in `project.godot`.

**Status: source-patch validation passed; native compilation and runtime validation pending.** The MCP validation workflow checked out official Godot 4.7.2 and successfully applied the patcher against the real upstream files in [validation run 36](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39772632209) and [run 35](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39772626551). It also passed the addon packaging and static installer assertions. This proves the patch anchors match and source edits are applied; it does **not** compile the C++ changes or test directory access to APK assets on Android. A full Android build and runtime test are still required.

### Build verification triggered for the integration branch

Commit `c88f18aa3e8fec316d8b378f47ff79a8ddbefbb6` makes relevant source/workflow changes on `feature/github-sync-and-safe-mcp` trigger the complete Android build automatically (README-only edits do not trigger it). This avoids relying only on the separate MCP ZIP validation workflow.

Current full Android build: [run 32](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39772776142). It is in progress as of this README update. Its result must confirm native C++ compilation, Gradle packaging of the bundled addon assets, ARM64-only ABI checks, APK integrity/signature/alignment, and the new final-APK MCP content assertions. Do not report success until that run finishes successfully.

### Source audit note (2026-10-22)

The upstream Android editor's `platform/android/java/editor/build.gradle` does not define a ready-made MCP addon installation hook. The current Android editor is built from the Godot native editor and its Android wrapper; the addon is a project-level `EditorPlugin`, not a native engine module. Therefore a Gradle-only copy of the ZIP would be packaging evidence, not a usable integration.

The next implementation should provide a deliberate **Install MCP into this project** flow from the patched Project Manager/editor, backed by a reproducible bundle included in the build. It must copy the plugin into the chosen project's `addons/godot_mcp_android`, validate that the destination is a Godot project, avoid overwriting an existing addon without a safe backup/confirmation, and enable the plugin only after the user confirms. The build must verify both that the bundle is inside the final APK and that the installer path can retrieve it. This approach preserves Godot's per-project plugin model instead of pretending the MCP plugin is globally active.

### Integration plan — do not skip the runtime boundary

1. Inspect the Android editor's project-loading and plugin lifecycle in Godot 4.7.2, and identify a supported way to make the addon available without silently enabling it in user projects or copying files into the APK with no usable install path.
2. Prefer a reproducible source/build integration that exposes a clear user-controlled install/enable action. Keep user projects isolated; never modify or delete project files unexpectedly.
3. Connect the safe-addon packaging job to the APK build only after the delivery mechanism is established. Add checks that inspect the final APK and prove the addon is actually reachable through that mechanism; an artifact ZIP beside the APK is not enough.
4. Add progressively stronger tests: Godot parser/import test, editor enable/disable test, scene edit + undo/redo test, loopback-only listener test, MCP client round-trip, then physical Android install/launch.
5. Keep the build ARM64-only (`arm64-v8a`), preserve the GitHub import patch, do not merge the draft PR without explicit permission, and update this README after each meaningful change or test.

## MCP coverage, hardening and remaining tests

- [Godot editor MCP coverage inventory](docs/MCP_EDITOR_COVERAGE.md) — exhaustive editor surfaces to audit, coverage states, acceptance criteria and safety boundaries.
- [Android MCP upstream capability audit](docs/ANDROID_MCP_UPSTREAM_AUDIT.md) — registered tool surface, concrete gaps and next engineering steps.
- CI pins the reviewed public upstream addon revision `5df91076250ece38ab182b2ca8b8a4a5d9a2d938` so packaging is reproducible.
- The packaging script removes generic expression execution, forces HTTP/WebSocket listeners to loopback, removes wildcard CORS, and patches scene-property changes and node removal to use Godot's editor undo/redo manager.
- File writes/edits still need a recovery strategy; the scene undo patches are source-level changes and are not yet verified by a successful package run or an on-device undo/redo test.

These are hardening changes and an audit baseline, not claims of complete editor coverage. The addon still needs successful CI packaging, installation in the actual Godot Android editor, and end-to-end testing with a compatible MCP client.

## New validation added — Godot headless parser/load check

Commit: `fc07465581a77c64fe1fe9799cc4a1c167b0d15f`

The MCP validation workflow now downloads the official Godot 4.7.2 Linux editor in CI, creates a temporary test project, enables the packaged addon, and starts the headless editor. The job fails if the editor exits unsuccessfully or logs script/parser/load errors. This is stronger than checking file names and text patterns, but it is **not** a substitute for running the Android APK on a physical phone or testing an MCP client roundtrip.

**Important unresolved Android installer risk:** the addon is currently embedded under the APK's raw Android `assets/mcp-addon/` directory, while the native Project Manager installer tries to read `res://mcp-addon`. Those are different resource namespaces unless the build explicitly mounts/copies the assets into Godot's virtual filesystem. The APK packaging checks alone do not prove that this path works. The new headless validation checks the addon itself, not this Android asset-copy path. The installer must remain marked as unverified until this mismatch is resolved and tested.

### Result — validation run 49

[Run 49 completed successfully](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39784806594) on 2026-10-22. The official Godot 4.7.2 headless editor loaded the MCP addon without script/parser errors, and the archive safety checks passed. This confirms the addon parses and loads in the Linux test project; it still does not confirm that the native Android installer can copy raw APK assets into a project. The installer resource-path risk above remains open.

The MCP validation workflow now runs on changes to its workflow files or scripts, rather than every README-only change.

## Android MCP installer asset-path fix — validation pending

Commits:
- Installer implementation: `8bd72e245a1b4b3e8c87eee01a63a97a5344344a`
- APK ZIP bundle: `a0654420c8763d49c90ea850db3594150b30eaac`
- Validation assertions updated: `4633269ebd66d216f91a0e6384a3704250f92f8e`

The installer no longer assumes raw Android APK assets are available at `res://mcp-addon`. The Android build now creates `assets/mcp-addon.zip`; the Project Manager patch reads that ZIP through Android's `AssetManager`, extracts only entries under `godot_mcp_android/`, rejects absolute/traversal paths, stages files under the project's `addons` directory, checks for `plugin.cfg`, and only then renames the staging folder and enables the plugin. It does not overwrite an existing addon folder or automatically delete a stale staging folder.

The first validation runs after this code change failed because a CI assertion still expected the old `copy_dir` implementation; that assertion has now been updated to check the ZIP/AssetManager path instead. **The updated validation and full Android compile are still pending**; do not treat the installer as proven until the new run passes and device testing is done.

### Updated result — asset installer checks passed

The updated MCP validation passed in [run 59](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39790155049) and [run 60](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39790161712). These runs verify the addon loads in Godot's Linux headless editor, the APK workflow contains the ZIP asset and safety checks, and the installer patch no longer relies on the invalid `res://mcp-addon` path. The full Android build is queued/running separately; C++ compilation and the final APK still need to pass before this change is considered build-verified.

### Compile-risk correction before final Android build

Commit `f54f1c3cd73eee346949a549d45c92035bb1b3a0` replaces an unsupported `FileAccess::open_absolute` call with Godot's supported `FileAccess::open` API for absolute filesystem paths. This was caught while cross-checking the patch against the upstream 4.7.2 headers. The new source commit triggers another full Android build; the earlier build may be superseded, so final C++/APK status remains pending.


### Android build run 39 — compiler failure and corrective retry

- [Run 39](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39790981418) reached native C++ compilation but failed in `editor/project_manager/project_manager.cpp`: `FileAccessAndroid::open()` is not an `Error`-returning instance API; it inherited the static `FileAccess::open()` factory, which returns `Ref<FileAccess>`. No APK artifact was produced.
- Commit `996a6df2e481b54e88d793700f5f23946f7cf592` changed the installer to hold the asset reader as `Ref<FileAccess>` and check `is_null()`. A follow-up cleanup in `ae360ab2c56a8677fa3b04679d607aea577de71e` removes the now-unneeded direct Android header include and consistently closes the reference.
- The replacement Android build workflow was queued at [run 39793879648](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39793879648) when this note was written. Its compiler result and final APK checks are still pending. The successful MCP packaging validation does not by itself prove the native editor build or on-device install.

### Validation assertion update — 2026-10-22

The first retry of the packaging validation correctly exposed a stale assertion that treated the literal `res://mcp-addon.zip` asset filename as the old invalid `res://mcp-addon` directory. The validation now checks for the forbidden `res://mcp-addon/` directory form and expects the current `Ref<FileAccess>` factory-based reader. Workflow correction commit: `6d088971040d76173eaeb97703aeb36ef482b15b`. Fresh validation and Android build runs for that commit are queued; neither has passed yet.

### Asset reader follow-up

The initial `Ref<FileAccess>` retry still routed the ZIP name through Godot's normal resource-path factory, which was not appropriate for the raw APK asset namespace. The installer now explicitly uses `FileAccessAndroid::open_internal("mcp-addon.zip", FileAccess::READ)` to access Android's AssetManager. The copy loop is bounded by the asset's declared length, preventing a possible zero-byte EOF loop on an exact 16 KiB multiple and treating short reads as errors. Validation assertions were updated to cover the direct AssetManager path and bounded read loop. Latest source commit for this fix: `85ce3504316778bc7104e78f619c20a80ab99be5`; validation update commit: `7bbff02fc506dbd3755daa433ef6b5e878265cc9`. A fresh full Android build and validation are still pending.


### Run 40 — [39805117373](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39805117373)

- **Result: success** (completed 2026-10-22 at 16:02 UTC).
- Full Android editor build and safe MCP addon packaging completed successfully.
- Final APK size: 179,500,681 bytes (about 171.2 MiB); artifact ZIP: about 84 MiB.
- APK checks passed: ZIP integrity, Android APK signature verification, ZIP alignment, ARM64-only ABI, and embedded MCP bundle checks.
- The package ID is now unique to this custom build: `org.godotengine.editor.v4.debug.prilcustom`. This avoids colliding with the standard Godot 4 debug editor package; it does not by itself resolve every possible Android installer failure.
- Signing certificate SHA-256: `217fdedb7f49b0b9018cb23de327099b38e4db319456ab6529096b224e970d5c`. Debug signing can still differ between CI runs, so do not assume an existing install can be upgraded in place.
- **Not yet proven:** installation or launch on the user's LG K51 / Android 11, or runtime installation and activation of MCP inside a project.
- Artifact: [godot-4.7.2-android-editor-arm64-only](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39805117373).


### Run 41 — [39813174735](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174735)

- **Status at 2026-10-22 16:31 UTC: in progress.** The native engine compilation step is still running; APK generation, ABI validation, signature verification, and artifact upload have not completed yet.
- The current workflow compiles ARM32 first and ARM64 second with `generate_android_binaries=yes` on the final SCons invocation. The APK validation step is configured to fail unless both `armeabi-v7a` and `arm64-v8a` are present.
- The separate safe MCP validation run [39813174855](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174855) completed successfully, including headless addon loading and packaging assertions.
- **Do not treat this run as a dual-ABI APK success until the build finishes and the final APK validation step passes.** No on-device installation or live MCP transport test has been demonstrated.
- The earlier Run 40 APK remains ARM64-only and is not the corrected deliverable.


### Run 41 — final result verified (2026-10-22)

- **Result: success.** [GitHub Actions run 39813174735](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174735) completed successfully.
- Downloadable artifact: [godot-4.7.2-android-editor-arm32-arm64](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174735/artifacts/12444807436) (artifact ID `12444807436`, ZIP size 174,784,829 bytes; expires 2026-11-21).
- Downloaded and inspected the actual artifact ZIP. It contains `godot-editor-arm32-arm64.apk` and `apk-badging.txt`. Artifact ZIP SHA-256: `09a298d4a86582ba4fee733ee2a3785ee5f944cfbf0ea55e3bdeec8b383a2e51`.
- APK size: 359,323,029 bytes. APK SHA-256 from the build log: `8ab4089907fc6aaed3eb62e6794bf4287e3cc3f4ce9f50389db3fd4f8573b06f`.
- Verified native ABIs in APK metadata and ZIP entries: `armeabi-v7a` and `arm64-v8a`. APK ZIP integrity passed.
- Android package ID: `org.godotengine.editor.v4.debug.prilcustom`; version name: `4.7.2.stable`.
- APK signature verification passed with APK Signature Scheme v2; ZIP alignment check passed.
- MCP payload is present in the APK: `assets/mcp-addon/plugin.cfg`, `assets/mcp-addon/scripts/protocol/mcp_tool_registry.gd`, and `assets/mcp-addon.zip`. The build checks also confirmed loopback-only HTTP/WebSocket bind addresses and rejected wildcard CORS and the generic script-evaluation/project-deletion tool registrations.
- Separate MCP validation [run 39813174855](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39813174855) also passed.
- **Still unverified:** installation/launch on the LG K51 (Android 11), successful in-app MCP addon installation, undo/redo behavior on device, and a real MCP client round-trip. A successful CI build is not a device test.


## Integration work in progress — public repository search and file recovery

As of 2026-10-22, the Project Manager GitHub dialog is being expanded from URL-only import to a single-field workflow that accepts either:
- a search query such as `godot mcp` or an account/repository name,
- a direct `owner/repository` identifier, or
- a GitHub repository URL.

A search query calls GitHub's public repository search API, presents up to 20 matching repositories, and lets the user choose one to import. Direct repository identifiers/URLs continue through the ZIP download/import flow. This is public-repository search only; private repositories and authenticated account access are not included.

The MCP package hardening script is also being expanded so `write_file` and `edit_file` save the previous contents to unique project-local recovery copies under `.godot_mcp_backups/` before changing an existing file. If a recovery copy cannot be created, the operation should abort before the original file is overwritten. The tool result reports the recovery-copy path.

**Status: source changes committed; deliberately not tested yet.** To respect the requested integration order, automatic Android builds and MCP validation have been paused and changed to manual dispatch. Do not install a new APK or call these features verified until the remaining integration work is complete and the full validation/build sequence is explicitly started.


### Latest integration changes — 2026-10-22 (not yet validated)

- Added a **“Recargar siguientes 20”** button to the public GitHub repository search results. It retains the current query and advances through GitHub Search API pages rather than repeating the first 20 repositories. After the available results (up to GitHub's 100-result search cap), the button returns to the first page.
- Reviewed Android build run [39828558952](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39828558952). The native build reached the modified Project Manager code and failed because the JSON parser passed `PackedByteArray::ptr()` as `const unsigned char *` to `String::utf8`, which expects `const char *`. The patch now casts the pointer explicitly. This correction is **not yet verified by a new full build**.
- MCP `write_file` and `edit_file` now verify that the recovery copy matches the original text before the original file can be overwritten. If the recovery copy cannot be verified, the operation aborts.
- These changes are source-only at this stage. No new APK has been produced from them, and the GitHub search UI, recovery behavior, final APK, and on-device MCP flow remain unverified until the planned integration is complete and validation is authorized.


## MCP coverage expansion — 2026-10-22 (source changes, not yet validated)

I expanded the Android MCP packaging script with five additional typed tools: `get_editor_state`, `open_scene`, `control_running_scene`, `get_node_properties`, and `create_resource`. I have now added two generic UI tools as well: `inspect_editor_ui` and `activate_editor_ui_control`. The validation workflow is being updated to require all seven scripts and registry entries in the final addon archive.

**This does not give an AI every Godot capability.** The MCP only exposes operations implemented as registered tools. It still lacks broad control of all menus, 2D/3D viewport actions, import/reimport, complete Inspector editing, animation and TileMap/TileSet editors, debugger/profilers, export presets, plugin-specific controls, and many dialogs. The full scope is tracked in [the MCP editor coverage inventory](docs/MCP_EDITOR_COVERAGE.md).

The five new tools are source changes only. They have not been run through the packaging workflow, the Godot headless parser, an MCP client, or the Android device. No new build or validation was launched, per the integration pause.


**Intended registered MCP tool count: 36** (source-derived and not yet runtime-confirmed). They cover connection/project info, editor state, scene tree and node edits, opening/running scenes, file search/read/write/edit, resource UID/validation/creation, filesystem scan, and editor logs. The unrestricted expression tool remains disabled. The number of tools is not the same as full Godot coverage: visual editor operations and many advanced workflows still require dedicated tools.

## Generic Godot editor UI bridge — source added, not yet validated

The package generator now creates two additional tools:

- `inspect_editor_ui`: lists live editor controls with exact paths, classes, labels, visibility, disabled state, tab titles, form values, and entries in open popup menus; long text previews are capped and secret LineEdit values are redacted.
- `activate_editor_ui_control`: activates an exact visible button or an item in an already-open `PopupMenu`, enabling navigation through UI options where Godot has no dedicated typed MCP operation.

This is a first bridge toward navigating the main toolbar, menus, docks, tabs, Output/Debugger panels, and less-used options. It does not yet prove every UI action is accessible, and complex controls (trees, inspectors, viewport tools, custom dialogs, plugin UI) will need more adapters. Project deletion/removal remains blocked; potentially destructive labels require an explicit confirmation flag. The unrestricted GDScript execution tool remains disabled.

Next scope is comprehensive inventory and implementation across main menus, context menus, workspace layout, scene tree, Inspector, filesystem/import, script editor, Output and Debugger details, profiling, 2D/3D, animation, TileMap/TileSet, resources, Project/Editor Settings, export, plugins, Android-specific UI, and every remaining obscure control or option.

**Status:** source changes only. No packaging workflow, parser validation, CI, Android build, or device test has been run for the two UI tools. The tool count is source-derived, not runtime-confirmed, and is not a claim of full editor coverage.


### Scene-tree organization — source added, not yet validated

The packaging script now generates three additional typed tools: `duplicate_node`, `rename_node`, and `reparent_node`. They use Godot's undo/redo history and include checks against root-node duplication/renaming collisions, self-descendant reparenting, and moving nodes into an instanced subscene. The validation workflow now expects these tool files and registry entries. Parser/runtime validation and real scene-tree/undo behavior remain pending; no tests or builds were launched for these changes.


### UI controls in scenes and preview preparation — source added, not yet validated

Added `inspect_scene_ui_controls` to enumerate Control nodes in the currently edited scene, including layout geometry and current widget state. Added `interact_scene_ui_control` for pressing buttons, changing text, range values and checkboxes, selecting options, and focusing controls. This enables programmatic inspection/exercising of scene UI nodes while building the interface.

**Runtime preview limitation:** these two tools address the edited scene tree, not a separate running-game process. Full interaction with live controls in a running preview still needs a tested remote-runtime or embedded-preview bridge. We will not claim that feature works until that bridge is implemented and tested.


### Embedded game preview input — source added, not yet validated

Added `send_editor_viewport_input`, which targets a specific `SubViewport` or `SubViewportContainer` in the editor UI and sends mouse clicks/motion, keyboard events, or text events. This is a path toward clicking game UI in an embedded preview. It deliberately does not claim to control an external game process; that case still needs a runtime bridge or supported debugger integration. No tests or builds have been launched.


### Additional scene organization — source added, not yet validated

Added `reorder_node` for sibling order, `set_node_group` for node groups, and `manage_node_signal` for connecting/disconnecting signals between scene nodes. The actions include undo/redo support where applicable and validate that the signal and target method exist. Runtime compatibility, ownership, and serialization remain unverified; no tests or builds were launched.


### Output and diagnostics — source added, not yet validated

Added `read_editor_diagnostics` to collect bounded text from visible editor labels, text editors, and rich-text controls. This is intended to read Output/Debugger text when the target editor exposes it in its UI tree. It does not yet cover structured debugger APIs or logs owned by a separate process. No tests or builds were launched.


### Live running-game control and fullscreen — source added, not yet validated

Two tools were added to bridge the editor MCP connection to the actual running game:

- `install_runtime_game_bridge`: with explicit `confirm_install=true`, installs a project-local autoload companion on loopback port `37843`. It refuses to overwrite an existing bridge and creates/verifies a backup of `project.godot` before editing its autoload section.
- `control_runtime_game`: connects to that running companion to inspect live `Control` nodes (paths, classes, labels/values and screen rectangles), click a control by node path, send mouse/key input, and switch the game window to fullscreen/windowed or toggle fullscreen.

This is the intended path for a game running as a separate process; the older `send_editor_viewport_input` remains the embedded-`SubViewport` path. The runtime companion listens on `127.0.0.1` only and checks a random token generated at installation, so another local client cannot issue commands without reading the project-local token. The bridge requires the project autoload to be installed and the game running; it does not grant universal control of arbitrary native OS dialogs or guarantee that every Android/editor launch mode exposes the game window. All of this is source-only and **not validated** yet: no packaging, parser validation, CI workflow, APK build, or device test was run. The intended registered tool count is now 36, pending actual packaging/runtime confirmation.


### GitHub project import — selected refs

The Project Manager GitHub import dialog now has an optional branch/tag/commit field. Leaving it empty downloads the repository's default branch; entering a ref builds a GitHub archive URL for that specific ref. The patcher rejects whitespace, query/fragment syntax, backslashes, path traversal-like `..` strings, and unsupported ref characters before requesting the archive. This remains source-level work until the Android editor is rebuilt and tested; no build or workflow was launched.


The runtime controller also exposes touchscreen tap/release and swipe events, plus mouse movement, so Android gameplay that uses Godot screen-touch events can be exercised. Coordinate scaling, orientation, and the target game's input handling still need device verification.


### Required verification gate

Before merging this branch, protect the previously working GitHub import/search behavior from regressions; if the recent URL-fallback refinements are included in a future approved build, check default branch, explicit branch/tag/commit, pagination, download failures, and malformed refs separately. Also establish the current APK's ABI/package status and on-device installation/runtime status. A green packaging workflow alone does not prove the updated fallback works in the Android UI or that the APK installs and launches on a device. Record source changes, build results, and physical-device results separately.


### Source-only checks for preview debug overlays

The Windows workflow `.github/workflows/validate-debug-overlay-source.yml` now checks patcher syntax and applies it to a clean official Godot 4.7.2 checkout. A separate Windows workflow, `.github/workflows/validate-debug-overlay-android-compile.yml`, is configured to compile the **ARM32 (`armeabi-v7a`) Android editor native engine first**, matching the LG K51 target—no Gradle APK packaging and no Linux runner. Its result is pending; no in-game runtime behavior is claimed until compilation succeeds and the toggles are exercised in the running preview.

## Proposed feature — Native 3D terrain editor (documented, not implemented)

**Status: idea documented only. Do not treat this as an existing Godot feature or as code already merged.** The project owner wants a terrain workflow integrated into the Godot editor, designed to remain usable on Android/mobile as well as desktop.

### Intended capabilities
- Create a 3D terrain and sculpt its height directly in the editor.
- Brush operations: raise/lower, smooth, flatten, and add visible relief; more advanced erosion or holes/caves can be evaluated later.
- Paint terrain with multiple textures/material layers and colors.
- Add and distribute objects such as grass, trees, rocks, and structures, with controls for density, scale, random rotation, and terrain alignment.
- Import/export heightmaps where practical.
- Support undo/redo, collision generation, and sensible rendering/performance behavior.
- Provide a dedicated, touch-friendly editor workspace/tooling rather than requiring the user to write scripts for routine terrain editing.

### Proposed implementation order
1. **Small native vertical slice:** create a terrain resource/node and editor tool that can sculpt a heightfield with raise/lower, smooth, and flatten brushes; save/reopen the result and support undo/redo.
2. **Texture and color painting:** multiple material layers, brush size/strength, and persistent paint data.
3. **Object placement:** paint/distribute foliage and other scenes across the surface.
4. **Advanced terrain features:** heightmap workflow, more relief tools, and investigate erosion/caves only after the core is stable.
5. **Performance and device validation:** measure editing responsiveness and runtime rendering on the intended Android device before raising default terrain resolution or adding costly effects.

### Constraints and acceptance criteria
- Prefer native source integration over depending on an external editor plugin, but keep the implementation modular and review compatibility/licensing before reusing third-party code.
- Keep the interface usable on a narrow mobile screen and provide conservative defaults suitable for the LG K51 / Android 11 / ARM32 target.
- Do not trade away existing editor features or visual quality as a blanket performance fix. Optimize based on measurements.
- A completed source patch, successful Windows source checks, a successful Android native compile, a packaged APK, and a successful on-device test are separate milestones and must be recorded separately.
- **No terrain implementation or terrain test has started as part of this documentation update.** The current active task remains waiting for the Android ARM32 native compile check for the debug-overlay patch.

### Current test being awaited — 2026-10-24
- **PASS — [Source-only debug overlay checks, run 40065262063](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40065262063)** on commit `09c9cf0`.
- **IN PROGRESS — [Android ARM32 native compile, no APK, run 40065262042](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40065262042)** on commit `09c9cf0`. This compiles the native editor target on a Windows runner and is not a full APK build. Its result is still pending; do not mark the C++ patch as compile-verified until it finishes successfully.

