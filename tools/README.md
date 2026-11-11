# Linux Godot agent tools

- `godot_project_sync.py`: authenticated, read-only snapshot pull client for the shared Godot project relay.
- `test_godot_project_sync.py`: unit tests for path validation, manifest validation, checksum verification and non-overwrite behavior.

The client is shipped separately from the engine binary and does not alter Android. See `docs/LINUX_HEADLESS_AGENT.md` for pairing requirements and commands.
