# Neon Command Center API adapter

This branch adds an additive HTTP adapter for the existing `command_center` schema in the separate Godot Web IA repository. It does not replace Live Link's WebSocket transport yet and does not enable remote file writes.

## Database migration

The additive migration is maintained in the integration repository:

- [002_live_link_command_leases.sql](https://github.com/decuvilan-lgtm/Godot-web-ia-integrada/blob/main/database/migrations/002_live_link_command_leases.sql)

It adds:
- `pairing_codes.workspace_id`, so one-time pairing is scoped to a workspace;
- `commands.claimed_by_device`, `claim_expires_at` and `attempt_count`, so a worker can lease a command and another worker can recover it after a crash;
- indexes and foreign-key/check constraints for those fields.

The migration has been applied to Neon project `Godot Command Center`, database `neondb`, branch `production`. The new columns were queried and verified. It is additive and does not remove existing data.

## Environment

Set these only in the relay service's secret environment, never in Git:

- `COMMAND_CENTER_DATABASE_URL`: Neon connection string for `neondb`. Use this dedicated variable so the legacy account API does not mistake the Command Center schema for its older `accounts/projects` schema.
- `COMMAND_CENTER_ADMIN_TOKEN`: a high-entropy administrator secret used only to create one-time pairing codes.
- `COMMAND_CENTER_ALLOWED_ORIGINS` (optional): comma-separated exact browser origins. Defaults to `https://godot-web-ia-integrada-rt2l.onrender.com`; do not use `*`.

The adapter intentionally fails closed (HTTP 503) when the database is not configured. It does not silently fall back to in-memory command storage.

Do not configure a paid Render plan. No Render settings or environment variables were changed by this branch.

## Agent-side client

`relay/command_center_client.py` provides an async client for an agent/controller process. It creates a command with a required idempotency key, reads its status and waits for a terminal result. The relay independently rejects missing, empty, non-string, or overlong keys; retries with the same key are accepted only when target, action and arguments match exactly. It requires HTTPS for remote relays; plain HTTP is permitted only for localhost tests with an explicit opt-in. The client repeats the same read-only action allowlist and does not retry command creation automatically.

Tests for this client use a local aiohttp test server; they do not connect to the production Render relay.

## HTTP API

All device requests use `Authorization: Bearer <device_credential>`. The credential is returned once at pairing; only its SHA-256 hash is stored in Neon.

| Method | Route | Permission |
|---|---|---|
| POST | `/v1/command-center/pairing-codes` | Admin header `X-Command-Center-Admin` |
| POST | `/v1/command-center/pair` | One-time code; returns device credential |
| POST | `/v1/command-center/commands` | `agent_controller` only |
| GET | `/v1/command-center/commands/next` | Matching `android_editor` or `web_editor` |
| POST | `/v1/command-center/commands/{id}/result` | Device holding the command lease |
| GET | `/v1/command-center/commands/{id}` | Paired device in the same workspace |

Pairing codes expire after two minutes and are single-use. Installation IDs are unique within a workspace. Commands expire after two minutes, leases last 45 seconds, and expired leases can be reclaimed up to five attempts. Every command must carry a 1–128 character idempotency key; retries with the same key are accepted only when target, action and arguments match exactly.

## Current command policy

The queue is deliberately read-only in this first adapter:
- `ping`
- `project.get_state`
- `project.list_files`
- `scene.inspect`
- `script.read`

Script/file writes, shell execution, arbitrary editor input and project deletion are not in the allowlist. This API does not yet add a poller to the Godot Web or Android plugins. The existing WebSocket Live Link still uses its legacy room/token protocol until a separately tested authentication bridge is implemented.

## Verification boundary

The adapter and routes are included in the relay's test suite. The CI workflow checks Python syntax and unit/protocol tests. Neon schema columns were verified after migration.

Not yet completed:
- relay deployed with `COMMAND_CENTER_DATABASE_URL` and admin secret;
- pairing of a real Android editor, web editor and controller;
- editor-side polling/claim/ack integration;
- WebSocket authentication unified with device credentials;
- durable project-file blob storage;
- Android device test or APK build.

Do not describe this adapter as end-to-end synchronization until those checks pass.
