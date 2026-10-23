# GitHub Analyze + Sync architecture

## Product intent

The GitHub repository is the authoritative source of truth for this workflow because the user delegates repository changes to the AI. The local Godot project is a working copy. A remote deletion is therefore a local deletion during a successful sync; it is not treated as a conflict by default. Local-only changes are reported and handled according to the sync policy, not silently preserved as if the remote were not authoritative.

The workflow must be explicit and fast:

1. **Analyze** fetches repository metadata and a recursive tree, compares it with a local inventory and the last successful sync manifest, then saves a reusable analysis snapshot.
2. **Review** displays added, modified, deleted, unchanged, ignored, and conflicted paths, plus byte counts and reasons.
3. **Sync** applies the analyzed plan without refetching/re-hashing unchanged content unnecessarily. It revalidates the remote commit and local files that are about to be overwritten/deleted. If either changed since analysis, it refreshes only the affected comparisons and asks for a new review when the plan materially differs.
4. **Verify** checks resulting file hashes and records the exact remote commit SHA as the last successful sync.

## UI and mobile placement (required)

Do not add a new always-visible control in the middle of the screen, and do not add a new row of buttons to the already crowded Project Manager toolbar. Integrate GitHub Sync with the existing selected-project sidebar/actions area, using the same button sizing, theme, spacing, and scroll container as the existing Edit / Run / Rename actions. Keep it next to related project actions rather than inventing a detached floating control.

- The entry action is available in the existing project-list sidebar and acts on the selected project. With no single valid project selected, explain the prerequisite and do not open a misleading sync flow.
- Open the workflow in the existing Project Manager content area/panel anchored to that sidebar action, not as a large centered modal that obscures the entire 720x1600 mobile interface. Reuse existing panel/dialog conventions where practical; if a compact confirmation dialog is unavoidable, constrain it to the viewport and keep the main workflow inline.
- Keep the workflow vertically scrollable. At a 720x1600 logical viewport, controls must remain reachable with the Android keyboard open, and text/buttons must not overflow horizontally. Do not hardcode desktop widths.
- **Analyze** is non-destructive and resolves the repository to an immutable commit before comparing files.
- **Review** lists additions, updates, tracked remote deletions, unchanged files, local-only files, ignored paths, and conflicts. Show destructive counts and the target commit.
- **Sync** stays disabled until a fresh analysis has been reviewed. It must confirm add/update/delete counts, then stage, validate, apply transactionally, verify, and roll back on failure.
- Secondary actions are **Refresh analysis**, **Cancel**, and **Open report**. Cancel removes temporary downloads before apply; during apply it triggers rollback.
- Show progress and actionable errors in the existing panel. Network requests must not block the UI thread. Do not duplicate generic file errors already reported by Godot's Output/Debugger.

## Repository model and fast comparison

- Resolve owner/repository and requested branch/tag/commit to an immutable commit SHA.
- Fetch the recursive Git tree for that commit; handle the truncated flag by falling back to paginated tree/content requests rather than silently accepting an incomplete inventory.
- Record path, Git object ID, type, size when available, mode, and commit SHA. Reject absolute paths, parent traversal, drive prefixes, and unsafe archive entries.
- Inventory the local project using normalized relative paths; ignore .git/, .godot/, editor cache, temporary files, and configured generated artifacts. Never follow symlinks outside the project root.
- Compare remote blob IDs and the saved manifest first. Hash local bytes only when required to distinguish local edits. Git blob IDs are SHA-1 over the bytes `blob <size>\0<bytes>`; do not compare a raw SHA-256 directly to a Git blob ID.
- Cache analysis by repository, commit SHA, canonical local project root/identity, ignore rules version, and manifest version. Reuse only if those inputs still match. A manifest is bound to one canonical project root and one repository URL; reusing it for another project or repository is a hard error, never a reason to continue with deletes.
- Do not download the whole repository archive merely to analyze it. Download file content only for changed/new files during sync; if archive download is used as a transport fallback, it is an apply-stage optimization, not the analysis source.

## Authoritative sync semantics

For a successful sync to the selected commit:

- Remote added file -> create locally.
- Remote modified file -> replace locally with the remote version.
- Remote deleted tracked file -> delete locally.
- Local-only file not present in the remote -> report as local-only; default policy is to leave untracked local-only files untouched unless the user selects “mirror exact repository”. This exception avoids deleting project assets the repo does not manage.
- A file known to the last successful manifest and removed remotely is tracked and MUST be deleted locally during sync.
- If a tracked local file was independently edited after analysis, the remote remains authoritative as requested, but show it in the plan and make the destructive overwrite/deletion count explicit before sync.
- Never delete paths outside the selected project root. Never follow symlinks. Never allow path traversal from repository tree names. The apply layer independently rejects delete operations for paths absent from the previous successful manifest, rejects add operations if a local file appeared after analysis, and re-hashes update/delete targets against the reviewed local hash before mutation.
- Preserve project-specific files only when explicitly configured as ignored/excluded; list exclusions in the report.

This reconciles the user's rule (“if it was deleted from the repo, delete it from the project”) with safe handling of unrelated local-only assets: previously tracked files deleted remotely are deleted. An optional exact-mirror mode can also remove all non-ignored local-only files.

## Transaction, rollback, and recovery

- Build a plan before modifying the project.
- Stage downloads in a temporary directory on the same filesystem where practical.
- Validate response codes, file sizes, checksums, paths, and the complete plan before apply.
- Write a transaction journal listing intended add/update/delete operations and backups.
- Move replaced/deleted tracked files into a per-sync backup until post-sync verification passes.
- Apply operations, verify final hashes and required project files, then atomically mark the manifest successful.
- On failure, roll back from the journal; if rollback itself fails, preserve backups and report exact recovery paths. Never mark a partial sync successful.
- Support cancellation before apply. During apply, cancellation must trigger rollback rather than leave a half-synced project.
- Avoid overwriting the MCP addon or other generated/managed folders unless they are tracked in the chosen repository plan.

## Persistent manifest

Use `project_manifest_path(metadata_root, project_root)` to derive a stable, distinct manifest path from the canonical project root using SHA-256, under the editor's per-project metadata/cache rather than the game project unless explicitly configured. Store a versioned manifest there. It records the canonical project root identity, repository URL, branch/ref, resolved commit SHA, normalized tracked paths and Git object IDs, ignore rules, last successful sync time, and the previous transaction ID. The manifest is written only after verification succeeds. The sync core now rejects a non-empty legacy manifest without project identity, a manifest whose project root differs from the selected root, and a manifest linked to another repository URL. The native Project Manager must still derive the selected project's own metadata path and pass that project root to the core.

## Android-first validation (no Linux editor build)

All product validation targets the Android editor and the LG K51-class mobile viewport. Do not compile the Linux editor or use Linux screenshots as a release gate.

1. Run Python syntax checks for patch scripts in CI; this is script validation, not a Linux editor build.
2. Apply the patches to a clean official Godot 4.7.2 source checkout and fail if any anchor is missing or duplicated.
3. Run unit tests for Git blob hashes, path safety, tree parsing, diff planning, manifest caching, transaction recovery, untracked-delete rejection, and stale-plan protection when local files change after analysis.
4. Exercise add/modify/delete/unchanged/local-only/ignored/stale-analysis cases; assert remote tracked deletions are actually removed locally.
5. Assert no operation can escape the selected Android project root and symlinks are never followed outside it.
6. Compile the actual Android editor for ARM32 and ARM64, package the full APK, and verify both ABIs, signature, APK contents, and addon assets.
7. Install and launch on Android 11 / LG K51; test network failures, cancellation, keyboard overlap, and viewport adaptation at 1600x720 and 720x1600 logical orientations as applicable.
8. Test Analyze -> Review -> Sync -> Verify on a real temporary Android project, including deletion and rollback.

Host-side syntax/unit checks may run in CI, but no Linux Godot editor build or Linux UI screenshot workflow is part of validation.

## Delivery status

The Python reference core now includes a stable per-project manifest-path helper, project/repository identity guards, and corresponding unit-test cases. A Python-only GitHub Actions workflow validates these unit tests on changes; a separate manual workflow checks native patch anchors against clean Godot 4.7.2 source and runs fixture checks without compiling or launching the editor. These workflows have been added but their results have not yet been observed. The native analyzer, GitHub HTTP integration, project-specific metadata-path selection, review dialog, and transactional sync are still not integrated into the Android Project Manager. The native Android UI and implementation must be added and validated against the actual Godot 4.7.2 source and an Android ARM32+ARM64 build before producing a release APK.
