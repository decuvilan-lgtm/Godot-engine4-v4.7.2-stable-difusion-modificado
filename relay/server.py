#!/usr/bin/env python3
"""Authenticated relay for optional Godot Live Link. Deploy behind TLS/WSS."""
import base64, binascii, hashlib, json, os, re, secrets, time
from aiohttp import WSMsgType, web

TOKEN = os.environ.get("LIVE_LINK_TOKEN", "")
ROOMS: dict[str, set[web.WebSocketResponse]] = {}
ROLES: dict[web.WebSocketResponse, str] = {}
LAST: dict[web.WebSocketResponse, dict[str, float]] = {}
PENDING: dict[str, dict[str, dict[str, object]]] = {}
SEEN_OPERATIONS: dict[str, dict[str, float]] = {}
MAX_PENDING_PER_ROOM = 1000
PENDING_TTL_SECONDS = 300.0
MAX_MESSAGE = 8 * 1024 * 1024
LIMITS = {"screen_frame": 3.0, "remote_input": 120.0, "project_operation": 20.0, "project_result": 60.0}
MAX_PROJECT_CONTENT = 5 * 1024 * 1024
PROJECT_ID_RE = re.compile(r"^[a-fA-F0-9-]{16,64}$")
OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")

def safe_relative_path(path):
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if chr(92) in path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    if any(part.lower() in (".git", ".godot") for part in parts):
        return False
    return True


def valid_project_operation(data):
    """Validate the transport envelope; the target must still validate before writing."""
    project_id, op_id, operation, path = (data.get(k) for k in ("project_id", "operation_id", "operation", "path"))
    # Fail closed: every agent operation must explicitly target the modified Android editor.
    if data.get("target_platform") != "android_editor" or data.get("policy_version") != 1:
        return False
    if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id): return False
    if not isinstance(op_id, str) or not OPERATION_ID_RE.fullmatch(op_id): return False
    if operation not in ("create", "update", "rename", "delete"): return False
    if not safe_relative_path(path): return False
    base = data.get("base_sha256", "")
    if not isinstance(base, str) or (base and not re.fullmatch(r"[a-fA-F0-9]{64}", base)): return False
    if operation in ("update", "rename", "delete") and not base: return False
    if operation in ("create", "update"):
        content = data.get("content_base64")
        digest = data.get("sha256")
        if not isinstance(content, str) or len(content) > (MAX_PROJECT_CONTENT * 4 // 3 + 8): return False
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest): return False
        try:
            raw = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError):
            return False
        if len(raw) > MAX_PROJECT_CONTENT or hashlib.sha256(raw).hexdigest() != digest.lower(): return False
    if operation == "rename" and not safe_relative_path(data.get("destination_path")):
        return False
    return True

async def health(_request):
    return web.json_response({"service":"godot-live-link-relay", "status":"ok"})

async def websocket(request):
    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE, heartbeat=25, compress=False)
    await ws.prepare(request)
    room = role = None
    try:
        first = await ws.receive(timeout=15)
        if first.type != WSMsgType.TEXT:
            await ws.close(message=b"join required"); return ws
        try: hello = json.loads(first.data)
        except Exception:
            await ws.close(message=b"invalid json"); return ws
        if not isinstance(hello, dict) or hello.get("type") != "join" or hello.get("role") not in ("controller", "target", "agent"):
            await ws.close(message=b"invalid join"); return ws
        requested = hello.get("room")
        if not isinstance(requested, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", requested):
            await ws.close(message=b"invalid room"); return ws
        if not TOKEN or not secrets.compare_digest(str(hello.get("token", "")), TOKEN):
            await ws.close(message=b"unauthorized"); return ws
        room, role = requested, hello["role"]
        peers = ROOMS.setdefault(room, set())
        if any(ROLES.get(p) == role and not p.closed for p in peers):
            await ws.close(message=b"role already connected"); return ws
        peers.add(ws); ROLES[ws] = role; LAST[ws] = {}
        await ws.send_json({"type":"joined", "room":room, "role":role, "peers":len(peers)})
        for peer in tuple(peers):
            if peer is not ws and not peer.closed: await peer.send_json({"type":"peer_joined", "role":role})
        async for msg in ws:
            if msg.type != WSMsgType.TEXT: continue
            if len(msg.data.encode("utf-8")) > MAX_MESSAGE: await ws.close(message=b"message too large"); break
            try: data = json.loads(msg.data)
            except Exception: continue
            if not isinstance(data, dict): continue
            kind = data.get("type")
            if kind not in LIMITS: continue
            if kind == "screen_frame":
                if role != "target": continue
                if not isinstance(data.get("data"), str) or len(data["data"]) > 6 * 1024 * 1024: continue
                w, h = data.get("width"), data.get("height")
                if type(w) is not int or type(h) is not int or not (1 <= w <= 1280 and 1 <= h <= 1920): continue
            elif kind == "remote_input":
                if role != "controller": continue
                ev = data.get("event")
                if not isinstance(ev, dict) or ev.get("kind") not in ("mouse_motion", "mouse_button", "key"): continue
                if ev.get("kind") in ("mouse_motion", "mouse_button"):
                    try: x, y = float(ev.get("x", -1)), float(ev.get("y", -1))
                    except (TypeError, ValueError): continue
                    if not (0 <= x <= 1 and 0 <= y <= 1): continue
            elif kind == "project_operation":
                if role != "agent" or not valid_project_operation(data): continue
            elif kind == "project_result":
                if role != "target" or not isinstance(data.get("project_id"), str) or not PROJECT_ID_RE.fullmatch(data["project_id"]) or not isinstance(data.get("operation_id"), str) or not OPERATION_ID_RE.fullmatch(data["operation_id"]) or data.get("status") not in ("applied", "rejected", "conflict", "failed"): continue
                expected = PENDING.get(room, {}).get(data["operation_id"])
                if expected is None or expected["project_id"] != data["project_id"]: continue
            now = time.monotonic(); previous = LAST[ws].get(kind, 0.0)
            # Matching pending results are one-shot; do not lose a real file-change result to rate limiting.
            if kind != "project_result":
                if previous and now - previous < 1.0 / LIMITS[kind]: continue
                LAST[ws][kind] = now
            if kind == "project_operation":
                pending = PENDING.setdefault(room, {})
                seen = SEEN_OPERATIONS.setdefault(room, {})
                for old_id, created_at in tuple(seen.items()):
                    if now - created_at > PENDING_TTL_SECONDS:
                        seen.pop(old_id, None)
                for old_id, entry in tuple(pending.items()):
                    if now - float(entry["created_at"]) > PENDING_TTL_SECONDS:
                        pending.pop(old_id, None)
                op_id = data["operation_id"]
                # Operation IDs are single-use for the TTL window, even after a result.
                if op_id in seen or len(pending) >= MAX_PENDING_PER_ROOM:
                    continue
                pending[op_id] = {"project_id": data["project_id"], "created_at": now}
                seen[op_id] = now
            elif kind == "project_result":
                PENDING.get(room, {}).pop(data["operation_id"], None)
            data["from_role"] = role
            encoded = json.dumps(data, separators=(",", ":"))
            for peer in tuple(peers):
                if peer is ws or peer.closed: continue
                if kind == "screen_frame" and ROLES.get(peer) == "controller": await peer.send_str(encoded)
                elif kind == "remote_input" and ROLES.get(peer) == "target": await peer.send_str(encoded)
                elif kind == "project_operation" and ROLES.get(peer) == "target": await peer.send_str(encoded)
                elif kind == "project_result" and ROLES.get(peer) == "agent": await peer.send_str(encoded)
    except (TimeoutError, ConnectionResetError): pass
    finally:
        ROLES.pop(ws, None); LAST.pop(ws, None)
        if room and ws in ROOMS.get(room, set()):
            peers = ROOMS[room]; peers.discard(ws)
            for peer in tuple(peers):
                if not peer.closed:
                    try: await peer.send_json({"type":"peer_left", "role":role})
                    except Exception: pass
            if not peers:
                ROOMS.pop(room, None)
                PENDING.pop(room, None)
                SEEN_OPERATIONS.pop(room, None)
    return ws

app = web.Application(client_max_size=MAX_MESSAGE)
app.router.add_get("/health", health)
app.router.add_get("/ws", websocket)
if __name__ == "__main__": web.run_app(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8765")))
