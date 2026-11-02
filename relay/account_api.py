"""First-party account/device API for the Godot editor relay.

The database is optional in local relay tests. If DATABASE_URL is absent, account
endpoints fail closed with 503; legacy Live Link token auth remains separate.
"""
from __future__ import annotations
import hashlib, hmac, os, re, secrets, uuid
from datetime import datetime, timezone
from aiohttp import web

MAX_TICKET_LENGTH = 256
PLATFORMS = {"linux", "android"}

def digest_secret(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()

def bearer_token(request: web.Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value or len(value) > 512:
        return None
    return value

async def startup(app: web.Application) -> None:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    app["account_db"] = None
    if not dsn:
        return
    import asyncpg
    app["account_db"] = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5, command_timeout=10)

async def cleanup(app: web.Application) -> None:
    pool = app.get("account_db")
    if pool is not None:
        await pool.close()

def database(request: web.Request):
    pool = request.app.get("account_db")
    if pool is None:
        raise web.HTTPServiceUnavailable(text="Account service database is not configured.")
    return pool

async def authenticated_device(request: web.Request):
    token = bearer_token(request)
    if token is None:
        raise web.HTTPUnauthorized(text="Bearer device credential required.")
    pool = database(request)
    row = await pool.fetchrow(
        """SELECT d.id AS device_id, d.account_id, d.platform, a.status AS account_status
           FROM devices d JOIN accounts a ON a.id=d.account_id
           WHERE d.credential_hash=$1 AND d.revoked_at IS NULL""", digest_secret(token))
    if row is None or row["account_status"] != "active":
        raise web.HTTPUnauthorized(text="Device credential is invalid or revoked.")
    await pool.execute("UPDATE devices SET last_seen_at=now() WHERE id=$1", row["device_id"])
    return row

async def enroll(request: web.Request) -> web.Response:
    pool = database(request)
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON body.")
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="Expected JSON object.")
    ticket = body.get("ticket")
    label = body.get("device_label")
    platform = body.get("platform")
    if not isinstance(ticket, str) or not (24 <= len(ticket) <= MAX_TICKET_LENGTH):
        raise web.HTTPBadRequest(text="Invalid enrollment ticket.")
    if not isinstance(label, str) or not (1 <= len(label.strip()) <= 80):
        raise web.HTTPBadRequest(text="Invalid device label.")
    if platform not in PLATFORMS:
        raise web.HTTPBadRequest(text="Unsupported device platform.")
    credential = secrets.token_urlsafe(48)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT id, account_id, intended_platform FROM enrollment_tickets
                   WHERE ticket_hash=$1 AND redeemed_at IS NULL AND revoked_at IS NULL
                     AND expires_at > now() FOR UPDATE""", digest_secret(ticket))
            if row is None or row["intended_platform"] != platform:
                raise web.HTTPUnauthorized(text="Enrollment ticket is expired, revoked, used or for another platform.")
            await conn.execute("UPDATE enrollment_tickets SET redeemed_at=now() WHERE id=$1", row["id"])
            device_id = await conn.fetchval(
                """INSERT INTO devices(account_id, device_label, platform, credential_hash)
                   " VALUES($1,$2,$3,$4) RETURNING id""",
                row["account_id"], label.strip(), platform, digest_secret(credential))
    return web.json_response({"device_id": str(device_id), "device_credential": credential,
                              "token_type": "Bearer", "account_id": str(row["account_id"])}, status=201)

async def list_devices(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    pool = database(request)
    rows = await pool.fetch(
        """SELECT id, device_label, platform, created_at, last_seen_at
           FROM devices WHERE account_id=$1 AND revoked_at IS NULL ORDER BY created_at""", identity["account_id"])
    return web.json_response({"devices": [dict(row) for row in rows]}, dumps=lambda obj: __import__("json").dumps(obj, default=str))

async def revoke_device(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    try:
        device_id = uuid.UUID(request.match_info["device_id"])
    except (ValueError, KeyError):
        raise web.HTTPBadRequest(text="Invalid device ID.")
    pool = database(request)
    result = await pool.execute(
        """UPDATE devices SET revoked_at=now() WHERE id=$1 AND account_id=$2 AND revoked_at IS NULL""",
        device_id, identity["account_id"])
    if result.endswith(" 0"):
        raise web.HTTPNotFound(text="Active device not found.")
    return web.json_response({"revoked": True, "device_id": str(device_id)})

async def list_projects(request: web.Request) -> web.Response:
    identity = await authenticated_device(request)
    pool = database(request)
    rows = await pool.fetch(
        """SELECT p.id, p.display_name, p.engine_version, p.head_revision, p.updated_at,
                  COALESCE(m.role, CASE WHEN p.account_id=$1 THEN 'owner' END) AS role
           FROM projects p LEFT JOIN project_members m ON m.project_id=p.id AND m.account_id=$1
           WHERE p.account_id=$1 OR m.account_id=$1 ORDER BY p.updated_at DESC""", identity["account_id"])
    return web.json_response({"projects": [dict(row) for row in rows]}, dumps=lambda obj: __import__("json").dumps(obj, default=str))

def install_account_routes(app: web.Application) -> None:
    app.router.add_post("/v1/devices/enroll", enroll)
    app.router.add_get("/v1/account/devices", list_devices)
    app.router.add_delete("/v1/account/devices/{device_id}", revoke_device)
    app.router.add_get("/v1/projects", list_projects)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
