# Linux Headless Project Sync Tools

- godot_project_sync.py downloads a verified, isolated snapshot from a shared Web project (list, sync/pull).
- godot_project_publish.py analyzes and publishes a local Godot project to a shared Web project (list, publish). Dry-run is the default; --apply is required to upload.

Both use the existing Render relay and a temporary agent_controller credential in GODOT_AGENT_TOKEN. No Neon/S3 credentials are used by clients.

Example:
    export GODOT_AGENT_TOKEN='(temporary agent_controller credential)'
    python3 tools/godot_project_publish.py list
    python3 tools/godot_project_publish.py publish PROJECT_UUID --project /path/to/project
    python3 tools/godot_project_publish.py publish PROJECT_UUID --project /path/to/project --apply

Publishing uses SHA-256 compare-and-swap checks and a three-way baseline. Conflicts stop the whole plan. It never deletes remote files, automatically pulls remote-only changes, or executes project code.
