#!/usr/bin/env python3
"""Publish a local Godot project to the existing shared-project relay.

Uploads are explicit, hash-checked and compare-and-swap protected. This tool
never deletes remote files, executes project code, or exposes storage credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_RELAY = "https://godot-web-ia-relay.onrender.com"
MAX_FILES = 10_000
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p8", ".asc", ".gpg", ".p12", ".pfx", ".keystore", ".jks", ".mobileprovision")
EXCLUDED_DIRS = {".git", ".godot", "__pycache__", ".venv", "venv", "node_modules"}


class PublishError(RuntimeError):
    pass


def validate_relative_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 1024:
        raise PublishError("Ruta vacía o demasiado larga.")
    if raw.startswith("/") or "\\" in raw or "\x00" in raw or ":" in raw or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise PublishError(f"Ruta no permitida: {raw!r}")
    parts = raw.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise PublishError(f"Ruta no segura: {raw!r}")
    lowered = [p.lower() for p in parts]
    if any(p in EXCLUDED_DIRS for p in lowered):
        raise PublishError(f"No se sincronizan metadatos ni caché: {raw!r}")
    if any(p in FORBIDDEN_NAMES or p.endswith(FORBIDDEN_SUFFIXES) or p == ".env" or p.startswith(".env.") for p in lowered):
        raise PublishError(f"Ruta sensible excluida: {raw!r}")
    name = lowered[-1]
    if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES) or name.endswith(".env") or name.startswith(".env."):
        raise PublishError(f"Archivo sensible excluido: {raw!r}")
    if name.endswith((".godot_sync_tmp", ".godot_sync_backup")):
        raise PublishError(f"Archivo temporal excluido: {raw!r}")
    return PurePosixPath(*parts).as_posix()


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise PublishError(f"Archivo supera 32 MiB: {path}")
            digest.update(chunk)
    return digest.hexdigest(), size


def scan_project(root: Path) -> dict[str, dict[str, Any]]:
    root = root.expanduser().resolve(strict=True)
    project_file = root / "project.godot"
    if not root.is_dir() or not project_file.is_file() or project_file.is_symlink():
        raise PublishError("La carpeta debe ser un proyecto Godot y contener un project.godot regular.")
    files: dict[str, dict[str, Any]] = {}
    total = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept = []
        for name in dirs:
            child = current_path / name
            lower_dir = name.lower()
            if (lower_dir in EXCLUDED_DIRS or child.is_symlink() or lower_dir in FORBIDDEN_NAMES
                    or lower_dir.endswith(FORBIDDEN_SUFFIXES) or lower_dir == ".env" or lower_dir.startswith(".env.")):
                continue
            kept.append(name)
        dirs[:] = kept
        for name in names:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            raw_rel = path.relative_to(root).as_posix()
            lower_name = name.lower()
            if (lower_name in FORBIDDEN_NAMES or lower_name.endswith(FORBIDDEN_SUFFIXES)
                    or lower_name.endswith(".env") or lower_name.startswith(".env.")):
                continue
            rel = validate_relative_path(raw_rel)
            digest, size = sha256_file(path)
            total += size
            if total > MAX_TOTAL_BYTES:
                raise PublishError("El proyecto supera el límite de 512 MiB.")
            files[rel] = {"path": rel, "sha256": digest, "byte_size": size, "local_path": path}
            if len(files) > MAX_FILES:
                raise PublishError(f"El proyecto supera el límite de {MAX_FILES} archivos.")
    names_set = set(files)
    for name in names_set:
        parts = name.split("/")
        for i in range(1, len(parts)):
            if "/".join(parts[:i]) in names_set:
                raise PublishError(f"Colisión entre archivo y carpeta: {name}")
    return files


def validate_manifest(payload: dict[str, Any], expected_id: str) -> tuple[int, dict[str, dict[str, Any]]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("project"), dict):
        raise PublishError("Manifiesto remoto inválido.")
    if payload["project"].get("id") != expected_id:
        raise PublishError("El manifiesto pertenece a otro proyecto.")
    revision = payload.get("head_revision")
    entries = payload.get("files")
    if not isinstance(revision, int) or revision < 0 or not isinstance(entries, list) or len(entries) > MAX_FILES:
        raise PublishError("Revisión o lista de archivos remotos inválida.")
    result: dict[str, dict[str, Any]] = {}
    total = 0
    for item in entries:
        if not isinstance(item, dict):
            raise PublishError("Entrada inválida en manifiesto remoto.")
        path = validate_relative_path(item.get("path"))
        digest, size = item.get("sha256"), item.get("byte_size")
        if path in result or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise PublishError(f"Hash o ruta remota inválida: {path}")
        if not isinstance(size, int) or size < 0 or size > MAX_FILE_BYTES:
            raise PublishError(f"Tamaño remoto inválido: {path}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise PublishError("El proyecto remoto supera 512 MiB.")
        result[path] = {"sha256": digest, "byte_size": size}
    for path in result:
        parts = path.split("/")
        if any("/".join(parts[:i]) in result for i in range(1, len(parts))):
            raise PublishError(f"Colisión de rutas en el manifiesto: {path}")
    return revision, result


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if new.scheme != "https" or old.scheme != new.scheme or old.hostname != new.hostname or old.port != new.port:
            raise PublishError("El relay intentó redirigir fuera de su origen HTTPS.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RelayClient:
    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise PublishError("La URL del relay debe ser HTTPS, sin credenciales, query ni fragmento.")
        self.base_url, self.token, self.timeout = base_url.rstrip("/"), token, timeout
        self.opener = urllib.request.build_opener(SameOriginRedirectHandler())

    def request(self, method: str, path: str, *, query: dict[str, str] | None = None,
                body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[bytes, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request_headers = {"Authorization": "Bearer " + self.token,
                           "Accept": "application/json, application/octet-stream",
                           "User-Agent": "godot-linux-headless-project-publisher/1.0"}
        if headers:
            request_headers.update(headers)
        req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                data = response.read(2 * 1024 * 1024)
                return data, response.headers
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", "replace")
            raise PublishError(f"Relay respondió HTTP {exc.code}: {detail}") from None
        except urllib.error.URLError as exc:
            raise PublishError(f"No se pudo conectar con el relay: {exc.reason}") from None

    def get_manifest(self, project_id: str) -> dict[str, Any]:
        data, _ = self.request("GET", f"/v1/command-center/projects/{urllib.parse.quote(project_id, safe='')}/manifest")
        try:
            return json.loads(data)
        except ValueError:
            raise PublishError("El relay devolvió JSON inválido.") from None

    def upload_file(self, project_id: str, path: str, data: bytes, digest: str, base_sha: str | None) -> dict[str, Any]:
        headers = {"X-File-SHA256": digest, "Content-Type": mimetypes.guess_type(path)[0] or "application/octet-stream"}
        if base_sha:
            headers["X-Base-SHA256"] = base_sha
        response, _ = self.request("POST", f"/v1/command-center/projects/{urllib.parse.quote(project_id, safe='')}/files",
                                   query={"path": path}, body=data, headers=headers)
        try:
            return json.loads(response)
        except ValueError:
            raise PublishError(f"Respuesta inválida al publicar {path}.") from None


def default_state_path(project_id: str) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "godot-project-sync" / f"{project_id}.json"


def load_state(path: Path, project_id: str) -> dict[str, Any]:
    if not path.exists():
        return {"project_id": project_id, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PublishError("No se pudo leer el punto de control local; no se publicó nada.") from None
    if not isinstance(data, dict) or data.get("project_id") != project_id or not isinstance(data.get("files"), dict):
        raise PublishError("El punto de control local no corresponde al proyecto.")
    return data


def build_plan(local: dict[str, dict[str, Any]], remote: dict[str, dict[str, Any]],
               state: dict[str, Any]) -> dict[str, list[str]]:
    baseline = state.get("files", {})
    plan = {"upload": [], "unchanged": [], "remote_only": [], "conflicts": []}
    for path in sorted(set(local) | set(remote) | set(baseline)):
        local_sha = local.get(path, {}).get("sha256", "")
        remote_sha = remote.get(path, {}).get("sha256", "")
        base = baseline.get(path, {}) if isinstance(baseline.get(path, {}), dict) else {}
        base_local, base_remote = base.get("local_sha256", ""), base.get("remote_sha256", "")
        if not baseline:
            if local_sha and not remote_sha:
                plan["upload"].append(path)
            elif local_sha and remote_sha and local_sha == remote_sha:
                plan["unchanged"].append(path)
            elif remote_sha and not local_sha:
                plan["remote_only"].append(path)
            elif local_sha and remote_sha:
                plan["conflicts"].append(path)
            continue
        local_changed = local_sha != base_local
        remote_changed = remote_sha != base_remote
        if not local_sha and remote_sha and not local_changed and not remote_changed:
            plan["remote_only"].append(path)
        elif local_changed and remote_changed:
            if local_sha == remote_sha:
                plan["unchanged"].append(path)
            else:
                plan["conflicts"].append(path)
        elif local_changed:
            if local_sha:
                plan["upload"].append(path)
            elif remote_sha:
                # Publish is intentionally non-destructive: local deletions never delete Web files.
                plan["remote_only"].append(path)
        elif remote_changed:
            if local_sha != remote_sha:
                # A remote deletion is not silently undone by a push-only client.
                plan["remote_only"].append(path)
        elif local_sha != remote_sha:
            # Keep Web-only edits visible until Linux receives them.
            plan["remote_only"].append(path)
        elif local_sha:
            plan["unchanged"].append(path)
    return plan


def save_state_atomic(path: Path, project_id: str, local: dict[str, dict[str, Any]],
                      remote: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "project_id": project_id, "files": {
        name: {"local_sha256": local.get(name, {}).get("sha256", ""),
               "remote_sha256": remote.get(name, {}).get("sha256", "")}
        for name in sorted(set(local) | set(remote))
    }}
    fd, temp_name = tempfile.mkstemp(prefix=".sync-state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def publish_project(client: RelayClient, project_id: str, root: Path, state_path: Path,
                    apply: bool = False) -> dict[str, Any]:
    local = scan_project(root)
    project_root = root.expanduser().resolve(strict=True)
    state_resolved = state_path.expanduser().resolve()
    if state_resolved == project_root or project_root in state_resolved.parents:
        raise PublishError("El archivo de estado debe estar fuera del proyecto Godot.")
    manifest = client.get_manifest(project_id)
    revision, remote = validate_manifest(manifest, project_id)
    state = load_state(state_path, project_id)
    plan = build_plan(local, remote, state)
    print(f"Proyecto: {manifest['project'].get('display_name', manifest['project'].get('slug', project_id))} · revisión Web {revision}")
    for label, paths in plan.items():
        print(f"{label}: {len(paths)}")
        for path in paths[:100]:
            print(f"  {path}")
        if len(paths) > 100:
            print(f"  … y {len(paths) - 100} más")
    if plan["conflicts"]:
        raise PublishError("Hay conflictos. No se publicó ningún archivo; revisa los hashes en ambos lados.")
    if not apply:
        print("Vista previa solamente. Añade --apply para publicar los archivos locales.")
        return plan
    for path in plan["upload"]:
        item = local[path]
        data = item["local_path"].read_bytes()
        if len(data) != item["byte_size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise PublishError(f"El archivo cambió después del análisis: {path}. Vuelve a ejecutar publish.")
        base_sha = remote.get(path, {}).get("sha256")
        result = client.upload_file(project_id, path, data, item["sha256"], base_sha)
        if result.get("sha256") != item["sha256"]:
            raise PublishError(f"El relay no confirmó el hash esperado para {path}.")
        print(f"Publicado: {path} · revisión {result.get('revision', '?')}")
    final_manifest = client.get_manifest(project_id)
    _, final_remote = validate_manifest(final_manifest, project_id)
    for path in plan["upload"]:
        if final_remote.get(path, {}).get("sha256") != local[path]["sha256"]:
            raise PublishError(f"La verificación final falló para {path}; el punto de control no avanzó.")
    # Keep the pre-transfer local hashes. Any edits made while uploading remain pending.
    save_state_atomic(state_path, project_id, local, final_remote)
    print(f"Publicación verificada · revisión Web {final_manifest['head_revision']} · punto de control actualizado.")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publica archivos de un proyecto Godot local en Godot Web.")
    parser.add_argument("--relay", default=os.environ.get("GODOT_RELAY_URL", DEFAULT_RELAY))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Lista los proyectos compartidos.")
    pub = sub.add_parser("publish", help="Analiza o publica el proyecto local hacia Godot Web.")
    pub.add_argument("project_id", help="UUID del proyecto compartido de destino.")
    pub.add_argument("--project", required=True, type=Path, help="Carpeta del proyecto Godot local.")
    pub.add_argument("--state", type=Path, help="Archivo de punto de control; por defecto se guarda en XDG_STATE_HOME.")
    pub.add_argument("--apply", action="store_true", help="Confirma la publicación de los archivos locales.")
    args = parser.parse_args(argv)
    token = os.environ.get("GODOT_AGENT_TOKEN")
    if not token:
        print("Falta GODOT_AGENT_TOKEN (credencial temporal emparejada como agent_controller).", file=sys.stderr)
        return 2
    try:
        client = RelayClient(args.relay, token)
        if args.command == "list":
            data, _ = client.request("GET", "/v1/command-center/projects")
            projects = json.loads(data).get("projects", [])
            for item in projects:
                print(f"{item.get('id')}  {item.get('slug')}  {item.get('display_name')}  rev={item.get('head_revision')}")
            return 0
        state_path = args.state or default_state_path(args.project_id)
        publish_project(client, args.project_id, args.project, state_path, args.apply)
        return 0
    except (PublishError, OSError, ValueError) as exc:
        print(f"Error de publicación: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
