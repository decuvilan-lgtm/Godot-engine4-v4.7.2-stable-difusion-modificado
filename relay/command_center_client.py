"""Agent-side HTTP client for the durable Neon Command Center queue."""
from __future__ import annotations

import asyncio
import time
from urllib.parse import urlsplit

import aiohttp

ALLOWED_ACTIONS = {
    "ping", "project.get_state", "project.list_files", "scene.inspect", "script.read"
}
ALLOWED_TARGETS = {"android_editor", "web_editor"}


class CommandCenterError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"Command Center HTTP {status}: {message}")
        self.status = status
        self.message = message


def validate_base_url(base_url: str, allow_insecure_localhost: bool = False) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("A Command Center base URL is required.")
    parsed = urlsplit(base_url.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Command Center URL must not contain credentials, query or fragment.")
    if parsed.path not in ("", "/"):
        raise ValueError("Command Center base URL must point to the service root.")
    host = (parsed.hostname or "").lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "https" and host:
        return base_url.strip().rstrip("/")
    if parsed.scheme == "http" and host in local_hosts and allow_insecure_localhost:
        return base_url.strip().rstrip("/")
    raise ValueError("Use HTTPS for remote Command Center URLs; HTTP is allowed only for explicit localhost testing.")


class CommandCenterClient:
    """Small agent-side client; never retries command creation without an idempotency key."""

    def __init__(
        self,
        base_url: str,
        device_credential: str,
        *,
        allow_insecure_localhost: bool = False,
        timeout_seconds: float = 10.0,
    ):
        self.base_url = validate_base_url(base_url, allow_insecure_localhost)
        if not isinstance(device_credential, str) or not (32 <= len(device_credential) <= 512):
            raise ValueError("A valid device credential is required.")
        if not (1 <= timeout_seconds <= 60):
            raise ValueError("Timeout must be between 1 and 60 seconds.")
        self._credential = device_credential
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        if self._session is None or self._session.closed:
            raise RuntimeError("Use CommandCenterClient inside an async context manager.")
        headers = {"Authorization": f"Bearer {self._credential}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        async with self._session.request(
            method, self.base_url + path, json=payload, headers=headers,
            allow_redirects=False,
        ) as response:
            try:
                body = await response.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError):
                body = {"error": (await response.text())[:1000]}
            if response.status >= 300:
                message = body.get("error") or body.get("message") or body.get("detail") or str(body)
                if 300 <= response.status < 400:
                    message = "Redirects are not allowed for authenticated Command Center requests."
                raise CommandCenterError(response.status, str(message))
            if not isinstance(body, dict):
                raise CommandCenterError(response.status, "Expected a JSON object response.")
            return body

    async def enqueue(
        self,
        *,
        target: str,
        action: str,
        args: dict | None = None,
        idempotency_key: str,
    ) -> str:
        if target not in ALLOWED_TARGETS:
            raise ValueError("Unsupported editor target.")
        if action not in ALLOWED_ACTIONS:
            raise ValueError("Action is not in the read-only policy.")
        if not isinstance(args if args is not None else {}, dict):
            raise ValueError("Command args must be a JSON object.")
        if not isinstance(idempotency_key, str) or not (1 <= len(idempotency_key) <= 128):
            raise ValueError("A stable idempotency key is required.")
        response = await self._request(
            "POST",
            "/v1/command-center/commands",
            payload={
                "target": target,
                "action": action,
                "args": args or {},
                "idempotency_key": idempotency_key,
            },
        )
        command_id = response.get("command_id")
        if not isinstance(command_id, str) or not command_id:
            raise CommandCenterError(502, "Command Center did not return a command ID.")
        return command_id

    async def get_command(self, command_id: str) -> dict:
        if not isinstance(command_id, str) or not command_id:
            raise ValueError("A command ID is required.")
        return await self._request("GET", f"/v1/command-center/commands/{command_id}")

    async def wait_for_result(
        self,
        command_id: str,
        *,
        timeout_seconds: float = 90.0,
        poll_interval: float = 1.0,
    ) -> dict:
        if not (1 <= timeout_seconds <= 600):
            raise ValueError("Wait timeout must be between 1 and 600 seconds.")
        if not (0.1 <= poll_interval <= 10):
            raise ValueError("Poll interval must be between 0.1 and 10 seconds.")
        deadline = time.monotonic() + timeout_seconds
        while True:
            result = await self.get_command(command_id)
            if result.get("status") in {"succeeded", "failed", "cancelled", "expired"}:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "Command result is still unknown; inspect its status before retrying."
                )
            await asyncio.sleep(min(poll_interval, remaining))
