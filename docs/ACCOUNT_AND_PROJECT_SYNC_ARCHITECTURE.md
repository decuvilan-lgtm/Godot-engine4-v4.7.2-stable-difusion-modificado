# Account and project sync architecture

**Status:** implementation specification; no cloud service is deployed and no account credential is embedded in a build yet.

## Product decision

The modified Linux and Android Godot editors will be clients of one first-party account and project service. Google/Firebase are not dependencies.

- **Render Web Service:** HTTPS/WSS API, device enrollment, authorization, sync coordination, change notifications and Live Link relay.
- **Neon PostgreSQL:** accounts, devices, projects, membership/permissions, file manifests, revisions, sync cursors, operation journal and audit metadata.
- **Object storage (S3-compatible, initially Cloudflare R2):** immutable project file blobs/chunks. Do not store large binary assets in PostgreSQL or proxy their bytes through the API unless required.
- **Linux Godot:** desktop client/agent; pairs with the account and exposes approved Live Link/MCP tools to the authorized ChatGPT bridge.
- **Android Godot:** user's primary editor; the APK can be provisioned for the account so first launch does not require interactive Google login.

## Credential and pairing model

Never bake an account password, database URL, Render secret, Neon credential, permanent bearer token or shared master key into either binary. Extracting an APK or Linux executable would expose it.

For the user's dedicated Android build, embed only a **single-use, short-lived enrollment ticket** scoped to one account and one installation slot. On first launch, Android redeems it over TLS; the server atomically consumes it and issues a device-specific revocable refresh credential. Android stores that credential in Android Keystore. The ticket must expire and be revocable before redemption. If the APK is copied before first activation, the first redemption could win; therefore treat the APK as private and allow the account owner to revoke the enrolled device.

Linux must not share Android's device secret. Pair it once using an authenticated device-pairing flow initiated from the already enrolled Android device (short-lived code/QR, explicit device label and confirmation). Linux receives its own revocable device credential and stores it in the OS credential store; if unavailable, use a permission-restricted local secret file and document the weaker protection. Do not put a live account credential in GitHub, build logs, release artifacts or source code.

The server must support device listing, last-seen status, credential rotation, logout and immediate revocation. ChatGPT does not need the user's password: an authorized bridge/tool session receives narrowly scoped, revocable project permissions. Installing a Godot addon alone does not grant ChatGPT access to this chat session; a real supported tool/connector route is still required and must be tested end-to-end.

## Efficient synchronization protocol

Use **local-first, manifest-based incremental sync** rather than uploading the whole project on every save.

1. Each client keeps a local SQLite sync index: project UUID, normalized relative path, file hash, size, last committed revision and local sync cursor.
2. Ignore .git/, .godot/, import caches, temporary/build output and configured exclusions by default. Never sync credentials or secrets by default.
3. For normal small files, hash the whole file (SHA-256). For large assets, split into content-defined chunks (FastCDC-style) and address each immutable chunk by SHA-256. Start with whole-file transfer for simplicity, add chunking only above a measured threshold.
4. Client asks the API which hashes are already stored; upload only missing blobs directly to object storage using short-lived signed URLs. Verify size and hash before commit.
5. Commit a new immutable manifest against base_revision using compare-and-swap. The API records a monotonically increasing project revision and an ordered change journal.
6. Other devices receive a lightweight notification (WebSocket; reconnect/poll fallback), request changes after their cursor and download only missing blobs. Verify hashes before materializing files.
7. Write to a temporary file, preserve a backup, then atomically replace where supported. Refresh/import the Godot FileSystem after applying.
8. Resume interrupted transfers by missing chunk hash; retries are idempotent.

For simultaneous edits, reject stale commits rather than silently using last-write-wins. Preserve both versions as conflict copies for the first release. Text/scene auto-merge can be added later after format-specific tests. Tombstones make deletions versioned and recoverable. Garbage collection may delete only unreferenced blobs after a safety retention period.

## Separate channels

- **Project cloud sync:** durable files and manifests; source of truth is the committed project revision.
- **Live Link:** low-latency commands, status, screenshots and operation acknowledgements.
- **Editor state:** selected node, open scene, tabs and viewport; ephemeral and not written into project files unless explicitly requested.

GitHub Sync remains an optional source-control/import feature, not a mandatory transport for every edit.

## API surface to implement

- POST /v1/devices/enroll — redeem one-time Android ticket.
- POST /v1/devices/pair and POST /v1/devices/pair/complete — pair Linux with an enrolled device using short-lived code and owner confirmation.
- GET /v1/account/devices, DELETE /v1/account/devices/{id}, POST /v1/devices/refresh, POST /v1/devices/revoke.
- GET/POST /v1/projects, GET /v1/projects/{id}/manifest, POST /v1/projects/{id}/commits.
- POST /v1/projects/{id}/blobs/check and signed upload/download URL issuance.
- GET /v1/projects/{id}/changes?after={cursor} and WebSocket change notifications.
- All routes enforce TLS, device authentication, project ACLs, size limits, rate limits and audit events. Signed blob URLs are short-lived and restricted to a single object and method.

## Delivery sequence and acceptance gates

1. Implement and test the account/device schema and enrollment/pairing API locally; no credentials in source.
2. Implement Linux pairing/client storage and expose connection status in the desktop Godot integration.
3. Implement Android ticket redemption and Keystore storage; build a private, account-provisioned APK only after the owner authorizes its creation.
4. Implement manifests, blob storage, incremental transfer, resumability and conflict preservation.
5. Add ChatGPT bridge authentication/authorization and prove an actual tool call reaches the selected Android project.
6. Run automated security, offline, interruption, duplicate, conflict, large-asset and regression tests; then build and test Android ARM32/ARM64 and the LG K51.

No service is deployed, no permanent token is embedded, and no end-to-end ChatGPT-to-Android connection is claimed until the relevant gates pass.