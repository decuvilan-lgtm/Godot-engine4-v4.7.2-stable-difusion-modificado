# Linux Headless Agent Runtime

## Scope and isolation

This is a separate Linux x86_64 runtime track. It does not modify the Android editor, Android source patcher, Android APK workflow, or Android release assets.

The runtime is built from the official Godot `4.7.2-stable` source. It is a full editor build that supports headless operation, not a reduced server-only engine and not the Android-customized engine.

## Build and verification

Run **Build Godot Linux Headless Agent Runtime** from Actions using `workflow_dispatch`, or push changes to the engine build workflow on the dedicated branch.

The workflow builds `platform=linuxbsd target=editor` for x86_64, verifies `--headless --version` and `--path`, and publishes a checksummed archive as a GitHub Release asset and 90-day Actions artifact.

## Shared-project synchronization client

The Linux runtime has a companion command-line synchronizer at `tools/godot_project_sync.py`. It connects to the existing Godot Web shared-project relay; it does not create a second agent. **ChatGPT remains the agent** that decides what to inspect, edit and test. Godot headless is the execution/runtime tool.

The client uses the existing API in `decuvilan-lgtm/Godot-web-ia-integrada`:

- `GET /v1/command-center/projects`
- `GET /v1/command-center/projects/{project_id}/manifest`
- `GET /v1/command-center/projects/{project_id}/files/content?path=...`

The client authenticates with a paired, temporary `agent_controller` bearer credential in the `GODOT_AGENT_TOKEN` environment variable. The relay URL defaults to `https://godot-web-ia-relay.onrender.com`; override it with `GODOT_RELAY_URL`. Credentials are not written to project files or printed. Prefer environment variables over command-line arguments so tokens do not appear in process listings.

### Commands

```bash
export GODOT_AGENT_TOKEN='(temporary agent_controller credential)'
python3 tools/godot_project_sync.py list

python3 tools/godot_project_sync.py sync PROJECT_UUID \
  --dest "$HOME/godot-agent/projects/my-project-r42"
```

`pull` is an alias for `sync`. The destination must be new; an existing project is never overwritten. The client validates the manifest, rejects unsafe paths, Git metadata, Godot cache and credential/signing files, downloads each file through the authenticated relay, checks size and SHA-256, stages the complete snapshot, then renames it into place.

Limits: 10,000 files, 32 MiB per file and 512 MiB total per snapshot.

**Current direction is intentionally one-way: shared Web project → isolated Linux snapshot.** The client does not upload, delete, overwrite, execute shell commands, or launch processes. Write-back is a separate future feature and must use compare-and-swap hashes, reviewed diffs, rescue copies and explicit approval.

After sync, import and validate separately:

```bash
./godot --headless --path "$HOME/godot-agent/projects/my-project-r42" --editor --quit
```

Synchronization never runs the project automatically. Import, scene tests and screenshot capture remain separate operations directed by ChatGPT.

### Pairing prerequisite and current limitation

The Relay already recognizes the `agent_controller` role for project-file API requests, but that does not mean this ChatGPT session is paired. A valid temporary device credential must be provisioned through the approved relay pairing flow and supplied to the runtime environment.

The CLI can be unit-tested without network credentials. A real end-to-end pull still requires a deployed relay, a paired `agent_controller`, and a shared project in the same workspace. Do not claim live transfer until that test succeeds.

## Validation

```bash
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m py_compile tools/godot_project_sync.py
```

The fast synchronization-client workflow runs these checks independently from the long Godot engine build and uploads a portable client package.

## Next integration stage

Add a project-side headless runner and a narrowly allowlisted bridge protocol. It should connect outward to the relay, authenticate with a dedicated short-lived device credential, and expose only project inspection, screenshots, state queries, and approved gameplay test actions. It must not expose arbitrary shell execution or unrestricted filesystem writes.
