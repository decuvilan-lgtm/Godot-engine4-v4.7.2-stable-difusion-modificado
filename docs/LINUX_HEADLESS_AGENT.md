# Linux Headless Agent Runtime

## Scope and isolation

This is a separate Linux x86_64 runtime track. It does not modify the Android editor, Android source patcher, Android APK workflow, or Android release assets.

The workflow checks out the official Godot `4.7.2-stable` source into a temporary GitHub Actions workspace, builds the Linux editor binary, and verifies that it starts with `--headless`. The generated executable is packaged as a persistent GitHub Release asset and as a 90-day Actions artifact.

The Linux binary is a full editor build that supports headless operation. It is not a reduced server-only engine and it does not include a project-specific agent bridge yet.

## Build and verification

Run **Build Godot Linux Headless Agent Runtime** from Actions using `workflow_dispatch`, or push changes to this workflow/documentation on the dedicated branch.

The workflow:
1. Builds only `platform=linuxbsd target=editor` for x86_64.
2. Runs `godot --headless --version`.
3. Verifies that the headless CLI exposes `--path`.
4. Packages the binary with a README and SHA-256 checksums.
5. Publishes the archive to the dedicated Linux runtime release.

## Next integration stage

After the executable build passes, add a project-side headless runner and a narrowly allowlisted bridge protocol. The runner should connect outward to the relay, authenticate with a dedicated short-lived device credential, and expose only project inspection, screenshots, state queries, and approved gameplay test actions. It must not expose arbitrary shell execution or unrestricted filesystem writes.

The runtime will receive a clean project snapshot from the shared-project synchronization service. It must not sync into or overwrite the Android editor installation.
