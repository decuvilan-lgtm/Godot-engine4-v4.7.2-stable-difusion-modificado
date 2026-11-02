"""Manifest and revision endpoints for incremental Godot project sync.

Large file bytes stay in S3-compatible object storage; this API only coordinates
verified content hashes and immutable manifests. Blob URL signing is a separate
storage adapter and is deliberately not faked here.
"""
from __future__ import annotations
import hashlib, json, re, uuid
from aiohttp import web
from account_api import authenticated_device, database

MAX_MANIFEST_FILES = 20000
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
IGNORED = {".git", ".godot"}

def safe_path(path: object) -> bool:
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if path.startswith("/") or "\\" in path or re.match(r"^[A-Za-z]:", path):
        return False
    parts = path.split("/")
    return all(p not in ("", ".", "..") and p.lower() not in IGNORED for p in parts)

def validate_manifest(files: object) -> tuple[bool, str]:
    if not isinstance(files, list) or len(files) > MAX_MANIFEST_FILES:
        return False, "files must be a bounded array"
    try:
        if len(json.dumps(files, separators=(",", ":")).encode()) > MAX_MANIFEST_BYTES:
            return False, "manifest too large"
    except (TypeError, ValueError):
        return False, "invalid manifest"
    seen = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            return False, "each file requires path, sha256 and size"
        path, digest, size = item["path"], item["sha256"], item["size"]
        if not safe_path(path) or path in seen:
            return False, "unsafe or duplicate path"
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
            return False, "invalid SHA-256"
        if type(size) is not int or not (0 <= size <= MAX_FILE_BYTES):
            return False, "invalid file size"
        seen.add(path)
    return True, ""

async def project_access(pool, identity, project_id, write=False):
    try:
        pid = uuid.UUID(project_id)
    except (ValueError, TypeError, AttributeError):
        raise web.HTTPBadRequest(text="Invalid project ID.")
    row = await pool.fetchrow(
        """SELECT p.id, p.account_id, p.head_revision,
                  COALESCE(m.role, CASE WHEN p.account_id=$2 THEN 'owner' END) AS role
           FROM projects p LEFT JOIN project_members m ON m.project_id=p.id AND m.account_id=$2
           WHERE p.id=$1 AND (p.account_id=$2 OR m.account_id=$2)""",
        pid, identity["account_id"])
    if row is None:
        raise web.HTTPNotFound(text="Project not found.")
    if write and row["role"] not in ("owner", "editor"):
        raise web.HTTPForbidden(text="Project is read-only for this device.")
    return row

async def get_manifest(request):
    identity = await authenticated_device(request)
    pool = database(request)
    project = await project_access(pool, identity, request.match_info["project_id"])
    revision = request.query.get("revision")
    if revision is None:
        revision = project["head_revision"]
    else:
        try: revision = int(revision)
        except ValueError: raise web.HTTPBadRequest(text="Invalid revision.")
    if revision < 0 or revision > project["head_revision"]:
        raise web.HTTPNotFound(text="Revision not found.")
    if revision == 0:
        return web.json_response({"project_id": str(project["id"]), "revision": 0, "files": []})
    exists = await pool.fetchval("SELECT 1 FROM project_revisions WHERE project_id=$1 AND revision=$2", project["id"], revision)
    if not exists:
        raise web.HTTPNotFound(text="Revision not found.")
    rows = await pool.fetch(
        """SELECT relative_path, file_sha256, byte_size FROM project_files
           WHERE project_id=$1 AND revision=$2 AND is_deleted=FALSE ORDER BY relative_path""",
        project["id"], revision)
    files = [{"path": r["relative_path"], "sha256": r["file_sha256"], "size": r["byte_size"]} for r in rows]
    return web.json_response({"project_id": str(project["id"]), "revision": revision, "files": files})

async def get_changes(request):
    identity = await authenticated_device(request)
    pool = database(request)
    project = await project_access(pool, identity, request.match_info["project_id"])
    try: after = int(request.query.get("after", "0"))
    except ValueError: raise web.HTTPBadRequest(text="Invalid cursor.")
    if after < 0: raise web.HTTPBadRequest(text="Invalid cursor.")
    rows = await pool.fetch(
        """SELECT sequence, revision, change_type, relative_path, device_id, created_at
           FROM project_changes WHERE project_id=$1 AND sequence>$2
           ORDER BY sequence LIMIT 1000""", project["id"], after)
    changes = [{"sequence": r["sequence"], "revision": r["revision"], "type": r["change_type"],
                "path": r["relative_path"], "device_id": str(r["device_id"]) if r["device_id"] else None,
                "created_at": r["created_at"].isoformat()} for r in rows]
    return web.json_response({"project_id": str(project["id"]), "changes": changes,
                              "next_cursor": changes[-1]["sequence"] if changes else after})

async def commit_manifest(request):
    identity = await authenticated_device(request)
    pool = database(request)
    project = await project_access(pool, identity, request.match_info["project_id"], write=True)
    try: body = await request.json()
    except Exception: raise web.HTTPBadRequest(text="Expected JSON body.")
    if not isinstance(body, dict) or set(body) != {"base_revision", "files"}:
        raise web.HTTPBadRequest(text="Expected base_revision and files.")
    base = body["base_revision"]
    if type(base) is not int or base < 0:
        raise web.HTTPBadRequest(text="Invalid base revision.")
    valid, error = validate_manifest(body["files"])
    if not valid: raise web.HTTPBadRequest(text=error)
    canonical = json.dumps(body["files"], sort_keys=True, separators=(",", ":"))
    manifest_hash = hashlib.sha256(canonical.encode()).hexdigest()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow("SELECT head_revision FROM projects WHERE id=$1 FOR UPDATE", project["id"])
            if current is None: raise web.HTTPNotFound(text="Project not found.")
            if current["head_revision"] != base:
                raise web.HTTPConflict(text=json.dumps({"error":"revision_conflict","head_revision":current["head_revision"]}),
                                       content_type="application/json")
            revision = base + 1
            await conn.execute(
                """INSERT INTO project_revisions(project_id,revision,parent_revision,author_device_id,manifest_sha256)
                   VALUES($1,$2,$3,$4,$5)""",
                project["id"], revision, base, identity["device_id"], manifest_hash)
            for item in body["files"]:
                await conn.execute(
                    """INSERT INTO project_files(project_id,revision,relative_path,file_sha256,byte_size,is_deleted)
                       VALUES($1,$2,$3,$4,$5,FALSE)""",
                    project["id"], revision, item["path"], item["sha256"], item["size"])
            await conn.execute(
                """INSERT INTO project_changes(project_id,revision,change_type,relative_path,device_id)
                   VALUES($1,$2,'update','', $3)""", project["id"], revision, identity["device_id"])
            await conn.execute("UPDATE projects SET head_revision=$2, updated_at=now() WHERE id=$1",
                               project["id"], revision)
    return web.json_response({"project_id":str(project["id"]), "revision":revision,
                              "parent_revision":base, "manifest_sha256":manifest_hash}, status=201)

def install_project_sync_routes(app):
    app.router.add_get("/v1/projects/{project_id}/manifest", get_manifest)
    app.router.add_get("/v1/projects/{project_id}/changes", get_changes)
    app.router.add_post("/v1/projects/{project_id}/commits", commit_manifest)
