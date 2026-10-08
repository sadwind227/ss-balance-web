"""本地接口的实际 HTTP 往返与访问边界。"""

from __future__ import annotations

import json
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.server import AppServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = AppServer()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, payload=None, token=True):
        headers = {"X-Local-Token": self.server.token} if token else {}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers=headers, method="POST" if payload is not None else "GET")
        with urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()

    def test_static_page_and_auth(self):
        status, html = self.request("/", token=False)
        self.assertEqual(status, 200)
        self.assertIn("整数平衡化", html)
        self.assertIn(self.server.token, html)
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/info", token=False)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()

    def test_job_lifecycle(self):
        options = {"number": "1234", "mode": "segment", "allow_multiple": False,
                   "target": 2, "budget": 30}
        status, body = self.request("/api/jobs", options)
        self.assertEqual(status, 201)
        job = json.loads(body)
        for _ in range(40):
            _, body = self.request("/api/jobs/" + job["id"])
            job = json.loads(body)
            if job["state"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(job["existence"], "yes")
        self.assertGreaterEqual(len(job["solutions"]), 2)
        self.assertTrue(all(item["verified"] for item in job["solutions"]))

    def test_invalid_input(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/jobs", {"number": "00123", "mode": "segment",
                                       "allow_multiple": False, "target": 5})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()

    def test_cancel_keeps_a_clear_state(self):
        options = {"number": "1919810", "mode": "segment", "allow_multiple": False,
                   "target": 20, "budget": 30}
        _, body = self.request("/api/jobs", options)
        job = json.loads(body)
        _, body = self.request("/api/jobs/" + job["id"] + "/cancel", {})
        cancelled = json.loads(body)
        self.assertIn(cancelled["state"], {"cancelled", "complete"})
        self.assertNotEqual(cancelled["existence"], "no")


if __name__ == "__main__":
    unittest.main()
