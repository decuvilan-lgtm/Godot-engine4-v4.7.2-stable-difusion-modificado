"""Tests for the agent-side Neon Command Center HTTP client."""
import unittest

from aiohttp import web
from aiohttp.test_utils import TestServer

from relay.command_center_client import (
    CommandCenterClient,
    validate_base_url,
)


class CommandCenterClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.poll_count = 0
        app = web.Application()

        async def create_command(request):
            self.assertEqual(request.headers.get("Authorization"), "Bearer " + "t" * 64)
            body = await request.json()
            self.assertEqual(body["target"], "android_editor")
            self.assertEqual(body["action"], "project.get_state")
            self.assertEqual(body["idempotency_key"], "test-operation-1")
            return web.json_response({"command_id": "cmd-test-1", "status": "queued"}, status=202)

        async def get_command(request):
            self.poll_count += 1
            if self.poll_count == 1:
                return web.json_response({"command_id": "cmd-test-1", "status": "claimed"})
            return web.json_response({
                "command_id": "cmd-test-1",
                "status": "succeeded",
                "ok": True,
                "result": {"project_name": "Sandbox"},
            })

        app.router.add_post("/v1/command-center/commands", create_command)
        app.router.add_get("/v1/command-center/commands/{command_id}", get_command)
        self.server = TestServer(app)
        await self.server.start_server()
        self.base_url = str(self.server.make_url("/")).rstrip("/")

    async def asyncTearDown(self):
        await self.server.close()

    def test_remote_http_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_base_url("http://example.com")

    def test_local_http_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            validate_base_url("http://127.0.0.1:8765")
        self.assertEqual(
            validate_base_url("http://127.0.0.1:8765", allow_insecure_localhost=True),
            "http://127.0.0.1:8765",
        )

    def test_remote_https_is_accepted(self):
        self.assertEqual(
            validate_base_url("https://relay.example.com/"),
            "https://relay.example.com",
        )

    async def test_enqueue_and_wait_for_result(self):
        async with CommandCenterClient(
            self.base_url,
            "t" * 64,
            allow_insecure_localhost=True,
        ) as client:
            command_id = await client.enqueue(
                target="android_editor",
                action="project.get_state",
                args={},
                idempotency_key="test-operation-1",
            )
            self.assertEqual(command_id, "cmd-test-1")
            result = await client.wait_for_result(
                command_id,
                timeout_seconds=2,
                poll_interval=0.1,
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["result"]["project_name"], "Sandbox")

    async def test_authenticated_requests_do_not_follow_redirects(self):
        target_hits = 0

        async def redirect(request):
            raise web.HTTPFound(location="/redirect-target")

        async def redirect_target(request):
            nonlocal target_hits
            target_hits += 1
            return web.json_response({"status": "succeeded"})

        self.server.app.router.add_get("/redirect", redirect)
        self.server.app.router.add_get("/redirect-target", redirect_target)

        async with CommandCenterClient(
            self.base_url,
            "t" * 64,
            allow_insecure_localhost=True,
        ) as client:
            with self.assertRaises(Exception) as raised:
                await client._request("GET", "/redirect")
            self.assertEqual(getattr(raised.exception, "status", None), 302)
        self.assertEqual(target_hits, 0)

    async def test_agent_client_rejects_write_actions(self):
        async with CommandCenterClient(
            self.base_url,
            "t" * 64,
            allow_insecure_localhost=True,
        ) as client:
            with self.assertRaises(ValueError):
                await client.enqueue(
                    target="android_editor",
                    action="script.write",
                    args={"path": "res://main.gd"},
                    idempotency_key="must-not-write",
                )


if __name__ == "__main__":
    unittest.main()
