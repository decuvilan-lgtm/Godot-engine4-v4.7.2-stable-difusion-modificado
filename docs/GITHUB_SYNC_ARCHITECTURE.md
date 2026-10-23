# GitHub Analyze + Sync architecture

## Product intent

The GitHub repository is the authoritative source of truth for this workflow because the user delegates repository changes to the AI. The local Godot project is a working copy. A remote deletion is therefore a local deletion during a successful sync; it is not treated as a conflict by default. Local-only changes are reported and handled according to the sync policy, not silently preserved as if the remote were not authoritative.

The workflow must be explicit and fast:

1. **Analyze** fetches repository metadata and a recursive tree, compares it with a local inventory and the last successful sync manifest, then saves a reusable analysis snapshot.
2. **Review** displays added, modified, deleted, unchanged, ignored, and conflicted paths, plus byte counts and reasons.
3. **Sync** applies the analyzed plan without refetching/re-hashing unchanged content unnecessarily. It revalidates the remote commit and local files that are about to be overwritten/deleted. If either changed since analysis, it refreshes only the affected comparisons and asks for a new review when the plan materially differs.
4. **Verify** checks resulting file hashes and records the exact remote commit SHA as the last successful sync.

## UI

Expose two primary actions in the GitHub panel:

- **Analyze**: non-destructive; enabled after a repository/project is selected.
- **Sync**: enabled only when a valid analysis snapshot exists. Shows the number of files to add/update/delete and the target commit before applying.

Secondary actions:

- **Refresh analysis**: reruns the comparison.
- **Cancel**: cancels network operations and removes temporary downloads.
- **Open report**: shows per-path results and errors.

On narrow mobile screens, primary buttons stack vertically or wrap; dialogs are constrained to the current viewport and their content scrolls. Progress, phase, and actionable error text are visible. Network requests must not block the UI thread.

## Repository model and fast comparison

- Resolve owner/repository and requested branch/tag/commit to an immutable commit SHA.
- Fetch the recursive Git tree for that commit; handle the truncated flag by falling back to paginated tree/content requests rather than silently accepting an incomplete inventory.
- Record path, Git object ID, type, size when available, mode, and commit SHA. Reject absolute paths, parent traversal, drive prefixes, and unsafe archive entries.
- Inventory the local project using normalized relative paths; ignore .git/, .godot/, editor cache, temporary files, and configured generated artifacts. Never follow symlinks outside the project root.
- Compare remote blob IDs and the saved manifest first. Hash local bytes only when required to distinguish local edits. Git blob IDs are SHA-1 over the bytes `blob <size>\0<bytes>`; do not compare a raw SHA-256 directly to a Git blob ID.
- Cache analysis by repository, commit SHA, project identity, ignore rules version, and manifest version. Reuse only if those inputs still match.
- Do not download the whole repository archive merely to analyze it. Download file content only for changed/new files during sync; if archive download is used as a transport fallback, it is an apply-stage optimization, not the analysis source.

## Authoritative sync semantics

For a successful sync to the selected commit:

- Remote added file -> create locally.
- Remote modified file -> replace locally with the remote version.
- Remote deleted tracked file -> delete locally.
- Local-only file not present in the remote -> report as local-only; default policy is to leave untracked local-only files untouched unless the user selects “mirror exact repository”. This exception avoids deleting project assets the repo does not manage.
- A file known to the last successful manifest and removed remotely is tracked and MUST be deleted locally during sync.
- If a tracked local file was independently edited after analysis, the remote remains authoritative as requested, but show it in the plan and make the destructive overwrite/deletion count explicit before sync.
- Never delete paths outside the selected project root. Never follow symlinks. Never allow path traversal from repository tree names.
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

Store a versioned manifest inside the editor's per-project metadata/cache, not in the game project unless explicitly configured. It records repository URL, branch/ref, resolved commit SHA, normalized tracked paths and Git object IDs, ignore rules, last successful sync time, and the previous transaction ID. The manifest is written only after verification succeeds.

## Tests required before Android compilation

1. Pure path and Git blob-hash unit tests.
2. Tree parsing: empty repo, nested files, symlinks, submodules, duplicate paths, invalid names, and truncated=true.
3. Diff cases: add, modify, delete, unchanged, local edit, local-only file, ignored file, branch changed, and stale analysis.
4. Sync tests against a temporary local fixture: success, HTTP failure, missing blob, disk-full/write failure, cancellation, crash recovery, rollback, and repeated idempotent sync.
5. Assert remote tracked deletions are actually removed locally.
6. Assert no operation can escape the selected project root.
7. UI tests at 1600x720 and 480x800, with keyboard open and long error text.
8. Build and inspect Linux editor first; only then run ARM32+ARM64 Android compilation and device install.

## Delivery status

This document defines the intended architecture. It does not claim that the analyzer, manifest, transactional sync, or tests are implemented yet. The native UI and implementation must be added and validated against the actual Godot 4.7.2 source before producing a release APK.
