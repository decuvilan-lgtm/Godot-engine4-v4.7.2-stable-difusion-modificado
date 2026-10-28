"""End-to-end tests for the external Live Link agent client and relay."""
import base64
import hashlib
import importlib.util
import os
import pathlib
import unittest

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ["LIVE_LINK_TOKEN"] = "test-token-live-link"
spec = importlib.util.spec_from_file_location("live_link_relay_client_tests", ROOT / "relay" / "server.py")
relay = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(relay)

from relay.agent_client import LiveLinkAgentClient, LiveLinkError  # noqa: E402

PROJECT_ID = "12345678-1234-1234-1234-123456789abc"
CONTENT = b"hello Godot"
CONTENT_B64 = base64.b64encode(CONTENT).decode("ascii")
CONTENT_SHA = hashlib.sha256(CONTENT).hexdigest()


class LiveLinkAgentClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        relay.ROOMS.clear()
        relay.ROLES.clear()
        relay.LAST.clear()
        relay.PENDING.clear()
        relay.SEEN_OPERATIONS.clear()
        app = web.Application(client_max_size=relay.MAX_MESSAGE)
        app.router.add_get("/ws", relay.websocket)
        self.server = TestServer(app)
        await self.server.start_server()
        self.url = str(self.server.make_url("/ws")).replace("http://", "ws://", 1)

    async def asyncTearDown(self):
        await self.server.close()
        relay.ROOMS.clear()
        relay.ROLES.clear()
        relay.LAST.clear()
        relay.PENDING.clear()
        relay.SEEN_OPERATIONS.clear()

    def operation(self, **overrides):
        data = {
            "type": "project_operation",
            "target_platform": "android_editor",
            "policy_version": 1,
            "project_id": PROJECT_ID,
            "operation_id": "agent-client-op-001",
            "operation": "create",
            "path": "Scenes/room.txt",
            "content_base64": CONTENT_B64,
            "sha256": CONTENT_SHA,
            "base_sha256": "",
        }
        data.update(overrides)
        return data

    async def test_client_round_trip_requires_explicit_target_result(self):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            target = await session.ws_connect(self.url)
            await target.send_json({
                "type": "join", "room": "agent_client_room",
                "role": "target", "token": "test-token-live-link"
            })
            self.assertEqual((await target.receive_json(timeout=2))["type"], "joined")
            async with LiveLinkAgentClient(
                self.url, "agent_client_room", "test-token-live-link", PROJECT_ID, timeout=2
            ) as agent:
                self.assertEqual((await target.receive_json(timeout=2))["type"], "peer_joined")
                import asyncio
                task = asyncio.create_task(agent.execute(self.operation()))
                received = await target.receive_json(timeout=2)
                self.assertEqual(received["type"], "project_operation")
                self.assertEqual(received["from_role"], "agent")
                self.assertEqual(received["project_id"], PROJECT_ID)
                await target.send_json({
                    "type": "project_result",
                    "project_id": PROJECT_ID,
                    "operation_id": received["operation_id"],
                    "status": "applied",
                    "message": "target confirmed",
                })
                result = await task
                self.assertEqual(result["status"], "applied")
                self.assertEqual(result["from_role"], "target")
            await target.close()

    async def test_client_rejects_wrong_project_and_missing_android_policy_before_send(self):
        async with LiveLinkAgentClient(
            self.url, "agent_validation_room", "test-token-live-link", PROJECT_ID, timeout=1
        ) as agent:
            with self.assertRaisesRegex(ValueError, "project_id"):
                await agent.execute(self.operation(project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            with self.assertRaisesRegex(ValueError, "policy"):
                await agent.execute(self.operation(policy_version=2))

    def test_insecure_remote_websocket_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "wss"):
            LiveLinkAgentClient("ws://example.com/ws", "room", "token", PROJECT_ID)
        # Loopback is permitted for local integration tests.
        client = LiveLinkAgentClient("ws://127.0.0.1:8765/ws", "room", "token", PROJECT_ID)
        self.assertEqual(client.project_id, PROJECT_ID)


if __name__ == "__main__":
    unittest.main()
