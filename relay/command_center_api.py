"""Durable Neon Command Center API for Godot Live Link.

This module is additive: it does not replace the existing Live Link WebSocket
transport or its legacy account endpoints. It provides a persistent, authenticated
command queue using the command_center schema. DATABASE_URL is optional locally;
all routes fail closed when it is absent.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from aiohttp import web

DEVICE_KINDS = {"android_editor", "web_editor", "agent_controller"}
EDITOR_KINDS = {"android_editor", "web_editor"}
ALLOWED_ACTIONS = {
    "ping",
    "project.get_state",
    "project.list_files",
    "scene.inspect",
    "script.read",
}
MAX_LABEL = 80
MAX_INSTALLATION_ID = 128
MAX_ARGS_BYTES = 256 * 1024
MAX_RESULT_BYTES = 1024 * 1024
MAX_IDEMPOTENCY_KEY = 128
CLAIM_SECONDS = 45


def digest_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_size(value: object) -> int:
    try:
        return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return MAX_ARGS_BYTES + 1


def _decode_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return value


def _pool(request: web.Request):
    pool = request.app.get("command_center_db")
    if pool is None:
        raise web.HTTPServiceUnavailable(text="Neon Command Center database is not configured.")
    return pool


async def startup(app: web.Application) -> None:
    dsn = os.environ.get("COMMAND_CENTER_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    app["command_center_db"] = None
    if dsn.strip():
        import asyncpg
        app["command_center_db"] = await asyncpg.create_pool(
            dsn=dsn.strip(), min_size=1, max_size=5, command_timeout=10
        )


async def cleanup(app: web.Application) -> None:
    pool = app.get("command_center_db")
    if pool is not None:
        await pool.close()


def _admin_authorized(request: web.Request) -> bool:
    expected = os.environ.get("COMMAND_CENTER_ADMIN_TOKEN", "")
    supplied = request.headers.get("X-Command-Center-Admin", "")
    return bool(expected) and bool(supplied) and hmac.compare_digest(expected, supplied)


async def authenticated_device(request: web.Request):
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 512:
        raise web.HTTPUnauthorized(text="Bearer device credential required.")
    pool = _pool(request)
    row = await pool.fetchrow(
        """SELECT id, workspace_id, device_kind, label
           FROM command_center.devices
           WHERE token_hash=$1 AND revoked_at IS NULL""",
        digest_secret(token),
    )
    if row is None:
        raise web.HTTPUnauthorized(text="Device credential is invalid or revoked.")
    await pool.execute(
        "UPDATE command_center.devices SET last_seen_at=now() WHERE id=$1", row["id"]
    )
    return row


async def create_pairing_code(request: web.Request) -> web.Response:
    if not _admin_authorized(request):
        raise web.HTTPUnauthorized(text="Command Center administrator credential required.")
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON body.")
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="Expected JSON object.")
    kind = body.get("device_kind")
    if kind not in DEVICE_KINDS:
        raise web.HTTPBadRequest(text="Unsupported device kind.")
    slug = body.get("workspace", "default")
    if not isinstance(slug, str) or not slug or len(slug) > 80:
        raise web.HTTPBadRequest(text="Invalid workspace slug.")
    pool = _pool(request)
    workspace_id = await pool.fetchval(
        "SELECT id FROM command_center.workspaces WHERE slug=$1", slug
    )
    if workspace_id is None:
        raise web.HTTPNotFound(text="Workspace not found.")
    code = secrets.token_urlsafe(24)
    await pool.execute(
        """INSERT INTO command_center.pairing_codes
           (workspace_id, code_hash, device_kind, expires_at)
           VALUES ($1,$2,$3,now() + interval '2 minutes')""",
        workspace_id, digest_secret(code), kind,
    )
    return web.json_response(
        {"pairing_code": code, "device_kind": kind, "workspace": slug, "expires_in_seconds": 120},
        status=201,
    )


async def pair_device(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON body.")
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="Expected JSON object.")
    code = body.get("pairing_code")
    label = body.get("label")
    installation_id = body.get("installation_id")
    if not isinstance(code, str) or not (24 <= len(code) <= 128):
        raise web.HTTPBadRequest(text="Invalid pairing code.")
    if not isinstance(label, str) or not (1 <= len(label.strip()) <= MAX_LABEL):
        raise web.HTTPBadRequest(text="Invalid device label.")
    if not isinstance(installation_id, str) or not (8 <= len(installation_id) <= MAX_INSTALLATION_ID):
        raise web.HTTPBadRequest(text="Invalid installation ID.")
    credential = secrets.token_urlsafe(48)
    pool = _pool(request)
    async with pool.acquire() as conn:
        async with conn.transaction():
            pairing = await conn.fetchrow(
                """SELECT id, workspace_id, device_kind
                   FROM command_center.pairing_codes
                   WHERE code_hash=$1 AND consumed_at IS NULL AND expires_at > now()
                   FOR UPDATE""",
                digest_secret(code),
            )
            if pairing is None:
                raise web.HTTPUnauthorized(text="Pairing code expired, used or invalid.")
            try:
                device_id = await conn.fetchval(
                    """INSERT INTO command_center.devices
                       (workspace_id, device_kind, label, installation_id, token_hash)
                       VALUES ($1,$2,$3,$4,$5) RETURNING id""",
                    pairing["workspace_id"], pairing["device_kind"], label.strip(),
                    installation_id, digest_secret(credential),
                )
            except Exception as exc:
                # asyncpg's UniqueViolationError is deliberately mapped without
                # exposing database details or consuming the pairing code.
                if exc.__class__.__name__ == "UniqueViolationError":
                    raise web.HTTPConflict(text="This installation is already paired to the workspace.")
                raise
            await conn.execute(
                """UPDATE command_center.pairing_codes
                   SET consumed_at=now(), consumed_by_device=$2 WHERE id=$1""",
                pairing["id"], device_id,
            )
            await conn.execute(
                """INSERT INTO command_center.events
                   (workspace_id, actor_device_id, event_type, payload)
                   VALUES ($1,$2,'device.paired',$3::jsonb)""",
                pairing["workspace_id"], device_id,
                json.dumps({"device_kind": pairing["device_kind"], "label": label.strip()}),
            )
    return web.json_response(
        {"device_id": str(device_id), "device_credential": credential, "token_type": "Bearer"},
        status=201,
    )


async def create_command(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    if identity["device_kind"] != "agent_controller":
        raise web.HTTPForbidden(text="Only an agent controller can enqueue commands.")
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON body.")
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="Expected JSON object.")
    target, action, args = body.get("target"), body.get("action"), body.get("args", {})
    key = body.get("idempotency_key")
    if target not in EDITOR_KINDS:
        raise web.HTTPBadRequest(text="Invalid command target.")
    if action not in ALLOWED_ACTIONS:
        raise web.HTTPBadRequest(text="Action is not enabled in the read-only command policy.")
    if not isinstance(args, dict) or _json_size(args) > MAX_ARGS_BYTES:
        raise web.HTTPBadRequest(text="Command arguments must be a bounded JSON object.")
    if key is not None and (not isinstance(key, str) or not (1 <= len(key) <= MAX_IDEMPOTENCY_KEY)):
        raise web.HTTPBadRequest(text="Invalid idempotency key.")
    pool = _pool(request)
    async with pool.acquire() as conn:
        async with conn.transaction():
            command_id = await conn.fetchval(
                """INSERT INTO command_center.commands
                   (workspace_id, origin_device_id, target, action, args, idempotency_key, expires_at)
                   VALUES ($1,$2,$3,$4,$5::jsonb,$6,now() + interval '2 minutes')
                   ON CONFLICT (workspace_id,idempotency_key) DO NOTHING
                   RETURNING id""",
                identity["workspace_id"], identity["id"], target, action,
                json.dumps(args), key,
            )
            if command_id is None and key is not None:
                existing = await conn.fetchrow(
                    """SELECT id, target, action, args, status FROM command_center.commands
                       WHERE workspace_id=$1 AND idempotency_key=$2""",
                    identity["workspace_id"], key,
                )
                if existing is None:
                    raise web.HTTPConflict(text="Idempotency key collision; retry with a new key.")
                if existing["target"] != target or existing["action"] != action or _decode_json(existing["args"]) != args:
                    raise web.HTTPConflict(text="Idempotency key was already used for a different command.")
                return web.json_response({
                    "command_id": str(existing["id"]), "target": existing["target"],
                    "action": existing["action"], "status": existing["status"], "reused": True,
                }, status=200)
            await conn.execute(
                """INSERT INTO command_center.events
                   (workspace_id, actor_device_id, event_type, payload)
                   VALUES ($1,$2,'command.queued',$3::jsonb)""",
                identity["workspace_id"], identity["id"],
                json.dumps({"command_id": str(command_id), "target": target, "action": action}),
            )
    return web.json_response({"command_id": str(command_id), "status": "queued"}, status=202)


async def claim_next_command(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    target = request.query.get("target", identity["device_kind"])
    if target not in EDITOR_KINDS or target != identity["device_kind"]:
        raise web.HTTPForbidden(text="A device can only claim commands for its own editor role.")
    pool = _pool(request)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """WITH candidate AS (
                     SELECT id FROM command_center.commands
                     WHERE workspace_id=$1 AND target=$2
                       AND expires_at > now()
                       AND (status='queued' OR
                            (status='claimed' AND claim_expires_at IS NOT NULL AND claim_expires_at < now()))
                       AND attempt_count < 5
                     ORDER BY priority DESC, created_at ASC
                     FOR UPDATE SKIP LOCKED LIMIT 1
                   )
                   UPDATE command_center.commands c
                   SET status='claimed', claimed_at=now(), claimed_by_device=$3,
                       claim_expires_at=now() + ($4::text || ' seconds')::interval,
                       attempt_count=attempt_count+1
                   FROM candidate WHERE c.id=candidate.id
                   RETURNING c.id,c.action,c.args,c.priority,c.expires_at,c.attempt_count""",
                identity["workspace_id"], target, identity["id"], CLAIM_SECONDS,
            )
            if row is None:
                return web.json_response({"command": None})
            await conn.execute(
                """INSERT INTO command_center.events
                   (workspace_id, actor_device_id, event_type, payload)
                   VALUES ($1,$2,'command.claimed',$3::jsonb)""",
                identity["workspace_id"], identity["id"],
                json.dumps({"command_id": str(row["id"]), "attempt": row["attempt_count"]}),
            )
    return web.json_response({
        "command": {
            "id": str(row["id"]), "action": row["action"], "args": _decode_json(row["args"]),
            "priority": row["priority"], "expires_at": row["expires_at"].isoformat(),
            "attempt": row["attempt_count"],
        }
    })


async def submit_command_result(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    if identity["device_kind"] not in EDITOR_KINDS:
        raise web.HTTPForbidden(text="Only an editor device can submit command results.")
    try:
        command_id = uuid.UUID(request.match_info["command_id"])
    except (ValueError, KeyError):
        raise web.HTTPBadRequest(text="Invalid command ID.")
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON body.")
    if not isinstance(body, dict) or type(body.get("ok")) is not bool:
        raise web.HTTPBadRequest(text="Expected an ok boolean and result object.")
    result = body.get("result", {})
    if not isinstance(result, dict) or _json_size(result) > MAX_RESULT_BYTES:
        raise web.HTTPBadRequest(text="Result must be a bounded JSON object.")
    duration = body.get("duration_ms")
    if duration is not None and (type(duration) is not int or not (0 <= duration <= 3600000)):
        raise web.HTTPBadRequest(text="Invalid duration.")
    pool = _pool(request)
    async with pool.acquire() as conn:
        async with conn.transaction():
            command = await conn.fetchrow(
                """SELECT id, workspace_id, status, target, claimed_by_device, claim_expires_at
                   FROM command_center.commands
                   WHERE id=$1 AND workspace_id=$2 FOR UPDATE""",
                command_id, identity["workspace_id"],
            )
            if command is None:
                raise web.HTTPNotFound(text="Command not found.")
            if command["target"] != identity["device_kind"] or command["claimed_by_device"] != identity["id"]:
                raise web.HTTPConflict(text="Command is not leased to this device.")
            existing = await conn.fetchrow(
                "SELECT ok,result FROM command_center.command_results WHERE command_id=$1",
                command_id,
            )
            if existing is not None:
                return web.json_response({
                    "command_id": str(command_id), "ok": existing["ok"],
                    "result": _decode_json(existing["result"]), "reused": True,
                })
            if command["status"] != "claimed" or command["claim_expires_at"] is None or command["claim_expires_at"] <= datetime.now(timezone.utc):
                raise web.HTTPConflict(text="Command lease expired; claim it again before submitting a result.")
            status = "succeeded" if body["ok"] else "failed"
            await conn.execute(
                """INSERT INTO command_center.command_results
                   (command_id,ok,result,duration_ms) VALUES ($1,$2,$3::jsonb,$4)""",
                command_id, body["ok"], json.dumps(result), duration,
            )
            await conn.execute(
                """UPDATE command_center.commands
                   SET status=$2, finished_at=now(), claim_expires_at=NULL
                   WHERE id=$1""",
                command_id, status,
            )
            await conn.execute(
                """INSERT INTO command_center.events
                   (workspace_id, actor_device_id, event_type, payload)
                   VALUES ($1,$2,'command.completed',$3::jsonb)""",
                identity["workspace_id"], identity["id"],
                json.dumps({"command_id": str(command_id), "status": status}),
            )
    return web.json_response({"command_id": str(command_id), "status": status, "ok": body["ok"]})


async def get_command(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    try:
        command_id = uuid.UUID(request.match_info["command_id"])
    except (ValueError, KeyError):
        raise web.HTTPBadRequest(text="Invalid command ID.")
    pool = _pool(request)
    row = await pool.fetchrow(
        """SELECT c.id,c.target,c.action,c.status,c.created_at,c.finished_at,
                  r.ok,r.result,r.error_code,r.error_message,r.duration_ms
           FROM command_center.commands c
           LEFT JOIN command_center.command_results r ON r.command_id=c.id
           WHERE c.id=$1 AND c.workspace_id=$2
             AND ( $3='agent_controller' OR c.target=$3 OR c.origin_device_id=$4 )""",
        command_id, identity["workspace_id"], identity["device_kind"], identity["id"],
    )
    if row is None:
        raise web.HTTPNotFound(text="Command not found.")
    return web.json_response({
        "command_id": str(row["id"]), "target": row["target"], "action": row["action"],
        "status": row["status"], "created_at": row["created_at"].isoformat(),
        "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
        "ok": row["ok"], "result": _decode_json(row["result"]),
        "error_code": row["error_code"], "error_message": row["error_message"],
        "duration_ms": row["duration_ms"],
    })


def install_command_center_routes(app: web.Application) -> None:
    app.router.add_post("/v1/command-center/pairing-codes", create_pairing_code)
    app.router.add_post("/v1/command-center/pair", pair_device)
    app.router.add_post("/v1/command-center/commands", create_command)
    app.router.add_get("/v1/command-center/commands/next", claim_next_command)
    app.router.add_post("/v1/command-center/commands/{command_id}/result", submit_command_result)
    app.router.add_get("/v1/command-center/commands/{command_id}", get_command)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
