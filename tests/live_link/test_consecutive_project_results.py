"""Functional regression: consecutive valid project results must not be rate-limited away."""
import asyncio
import importlib.util
import os
import pathlib
import unittest

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ["LIVE_LINK_TOKEN"] = "test-token-live-link"
spec = importlib.util.spec_from_file_location("live_link_relay_consecutive", ROOT / "relay" / "server.py")
relay = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(relay)


class ConsecutiveProjectResultTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        relay.ROOMS.clear()
        relay.ROLES.clear()
        relay.LAST.clear()
        relay.PENDING.clear()
        relay.SEEN_OPERATIONS.clear()
        app = web.Application(client_max_size=relay.MAX_MESSAGE)
        app.router.add_get("/ws", relay.websocket)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        relay.ROOMS.clear()
        relay.ROLES.clear()
        relay.LAST.clear()
        relay.PENDING.clear()
        relay.SEEN_OPERATIONS.clear()

    async def join(self, role):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"type": "join", "room": "consecutive_results", "role": role, "token": "test-token-live-link"})
        joined = await ws.receive_json(timeout=2)
        self.assertEqual(joined["type"], "joined")
        return ws

    async def test_two_consecutive_results_for_distinct_pending_operations_arrive(self):
        target = await self.join("target")
        agent = await self.join("agent")
        await target.receive_json(timeout=2)  # peer_joined

        project_id = "12345678-1234-1234-1234-123456789abc"
        for op_id in ("op-result-1", "op-result-2"):
            await agent.send_json({
                "type": "project_operation",
                "target_platform": "android_editor",
                "policy_version": 1,
                "project_id": project_id,
                "operation_id": op_id,
                "operation": "create",
                "path": f"tests/{op_id}.txt",
                "content_base64": "YQ==",
                "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
                "base_sha256": "",
            })
            forwarded = await target.receive_json(timeout=2)
            self.assertEqual(forwarded["operation_id"], op_id)
            # Operation messages are rate-limited; wait beyond 20/s before registering the next one.
            await asyncio.sleep(0.06)

        # Deliberately emit valid results back-to-back: neither may be dropped by the 60/s limiter.
        for op_id in ("op-result-1", "op-result-2"):
            await target.send_json({
                "type": "project_result",
                "project_id": project_id,
                "operation_id": op_id,
                "status": "applied",
                "message": "functional test result",
            })

        received = [
            await agent.receive_json(timeout=2),
            await agent.receive_json(timeout=2),
        ]
        self.assertEqual([item["operation_id"] for item in received], ["op-result-1", "op-result-2"])
        self.assertTrue(all(item["type"] == "project_result" for item in received))
        self.assertTrue(all(item["from_role"] == "target" for item in received))
        with self.assertRaises(asyncio.TimeoutError):
            await agent.receive(timeout=0.15)
        await agent.close()
        await target.close()


if __name__ == "__main__":
    unittest.main()
