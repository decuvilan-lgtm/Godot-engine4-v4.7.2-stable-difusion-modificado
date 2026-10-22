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

## Planned Android ABI support: ARM32 and ARM64

**Goal: provide compatible editor builds for both 32-bit ARM and 64-bit ARM Android devices. This is not implemented or verified yet.**

- The current workflow builds an ARM64-only APK with `arm64-v8a`; it is not an ARM32 build.
- Investigate whether the official Godot 4.7.2 Android **editor** and its native dependencies can be built and packaged for `arm32` / `armeabi-v7a`. Do not assume editor support just because exporting 32-bit Android games is supported.
- If supported, build and validate separate ARM32 and ARM64 editor APK artifacts, or a combined APK only if Godot's packaging and dependency setup supports it reliably. Separate APKs are easier to validate and avoid unnecessary package size.
- Validate each artifact's native ABI metadata, ZIP integrity, signature, size, and installation/launch on a matching physical device or emulator.
- Keep ARM64 support intact while investigating ARM32. Do not label an artifact ARM32-compatible until its ABI metadata and installation have been verified.

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

**Status: implementation committed; source-patch validation and native compilation pending.** The MCP validation workflow has been updated to check out official Godot 4.7.2, apply the patcher against real upstream files, and assert that the installer/safety checks are present. Watch [validation run 35](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/39772626551). Even if this passes, it only proves the patch applies; it does not compile the C++ changes or test directory access to APK assets on Android. A full Android build and runtime test are still required.

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
