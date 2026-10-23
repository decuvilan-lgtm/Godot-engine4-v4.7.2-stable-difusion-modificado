# Repository audit — 2026-10-23

## Scope and method

Read-only source review of the working branch `work/mobile-ui-preflight`, the GitHub Project Manager patcher, Android build workflow, MCP packaging patcher, preview debugger patcher, architecture documents, and validation workflows. No Linux editor test, Linux UI capture, compilation, device command, merge, release, or APK publication was initiated as part of this audit.

The GitHub search/import/run path has been manually exercised by the user on the LG K51: the user searched GitHub, imported their own public repository, and ran the imported project successfully. This is stronger evidence than static assertions for that exact path, but it does not prove every optional ref, pagination, and failure case.

## Findings by priority

### P1 — Analyze/Sync is specified, not implemented

The repository contains `docs/GITHUB_SYNC_ARCHITECTURE.md`, but no native Analyze/Sync implementation, persistent manifest, diff planner, transactional apply/rollback, or deletion reconciliation was found in the current project tree. The existing GitHub button imports a public repository archive; it is not synchronization.

**Status:** pending implementation. Do not advertise Analyze/Sync as working.

### P1 — Scene-aware import and the corrupt-file alert are requirements, not implementation

`docs/ANDROID_SCENE_IMPORT_ARCHITECTURE.md` and scene fixtures describe preserving scenes, dependencies, and reporting only truly damaged/unreadable files. The current Project Manager patch adds GitHub archive import and MCP installation, not the required scene-aware import system or the narrow corruption popup.

**Status:** pending implementation and Android validation.

### P1 — Linux editor validation conflicted with the Android-only requirement

The branch still had a Linux/Xvfb UI capture workflow and a Linux Godot headless MCP parser/load workflow. They are now disabled with `if: false` in this branch:
- `.github/workflows/mobile-ui-xvfb-capture.yml`
- `.github/workflows/validate-mcp-addon.yml`

The scene-import preflight is also disabled. These commits prevent those jobs from running; they do not delete the workflow files. The Android build workflow uses a Linux runner to cross-compile an **Android** target, which is distinct from building/testing the Linux editor.

### P2 — Android build automation does not automatically follow this working branch

`.github/workflows/build-godot-android-source.yml` is configured for push-triggered builds on `feature/github-sync-and-safe-mcp`, plus manual dispatch. It does not automatically build `work/mobile-ui-preflight`. No build was launched during this audit, to avoid starting a long compilation without explicit need.

**Status:** branch/workflow alignment is a delivery decision; manual dispatch is possible, but no new APK is claimed by this audit.

### P2 — MCP code has meaningful safeguards, but remains unverified on-device

The packaging patcher statically enforces typed tools, removes the generic expression-evaluation tool, rejects project deletion registration, pins the upstream addon revision, forces HTTP/WebSocket loopback binding, removes wildcard CORS, adds recovery copies for existing file writes/edits, and adds undo/redo integration to selected scene mutations. These are useful source-level controls, not proof of runtime safety or complete editor coverage.

A concrete failure-recovery gap remains in the native MCP installer: after the staged addon folder is renamed into the project, failure to save `project.godot` reports an error but does not automatically remove the installed addon folder or restore the original config. The plugin is described as disabled, but the filesystem operation is not fully rolled back.

**Status:** keep MCP expansion behind Android build/install and live mutation/undo tests. Do not claim full Godot control.

### P2 — GitHub optional-reference path needs separate coverage

The user-confirmed default public repository import works. The code also accepts an optional branch/tag/commit field and encodes it into the archive URL, but this audit did not test slash-containing branch names, tags/SHAs, rate limits, interrupted downloads, or storage exhaustion. These are unverified edge cases, not confirmed defects.

### P3 — Import cleanup and resource limits could be hardened

The downloaded archive uses a fixed cache filename, removes a previous copy before starting, and is reused by Godot's existing project installer. The completed archive is not explicitly deleted after successful import, and no explicit maximum archive size is enforced by the patch. This is a cache/storage hygiene improvement, not evidence that the user's successful import is broken.

### P3 — Documentation had stale statements

The README had a dated build status and a claim that the Linux UI preflight was part of the validation path. The README now records the user's Android confirmation, marks the older CI section as historical, and says the Linux UI preflight is disabled. The MCP upstream audit now reflects the pinned upstream revision and current recovery-copy patch rather than claiming those copies are absent.

## Verified / unverified matrix

| Area | Audit conclusion |
|---|---|
| GitHub search, import of user's public repo, run imported project | User-confirmed on LG K51 |
| Search pagination and ref field (branch/tag/commit) | Code present; edge cases not device-tested |
| Android dual-ABI build artifact in this audit | No new build initiated; no new artifact claimed |
| Analyze/Sync, manifest, transactions, remote-deletion handling | Not implemented in current tree |
| Scene-aware import / dependency copying | Architecture and fixtures only |
| Narrow corrupt/unreadable-file popup | Not implemented in current tree |
| Preview pause/resume/step/stop/mute | Patch script present; Android runtime unverified |
| MCP tool package and editor/runtime control | Source-generation present; live Android round-trip unverified |
| Linux Godot headless and Linux UI/Xvfb workflows | Disabled in this branch |
| Merge, release, APK publication | Not performed |

## Recommended order

1. Preserve the working GitHub import path; avoid changing it without a demonstrated defect.
2. Add Android-focused coverage for explicit refs, pagination, download failure/retry, and large archives.
3. Implement Analyze/Sync as a separate native workflow with immutable commit snapshots, Git blob comparison, a persistent manifest, staging, backups, rollback, and tracked remote deletions.
4. Implement the scene-aware import/corruption-report requirements without duplicating Output/Debugger diagnostics.
5. Only then resume MCP expansion and validate mutations, undo/redo, installer rollback, runtime input, and fullscreen on Android.
