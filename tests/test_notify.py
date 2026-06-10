import json
import os
import tempfile
import unittest

from orch import notify


class NotifyTest(unittest.TestCase):
    def setUp(self):
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            os.environ.pop(k, None)

    def test_resolve_creds_from_env(self):
        os.environ["ORCH_TG_TOKEN"] = "tok"
        os.environ["ORCH_TG_CHAT"] = "123"
        self.assertEqual(notify.resolve_creds(), ("tok", "123"))

    def test_resolve_creds_from_config_file(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "telegram.json")
        with open(path, "w") as f:
            json.dump({"token": "ftok", "chat_id": 999}, f)
        os.environ["ORCH_TG_CONFIG"] = path
        self.assertEqual(notify.resolve_creds(), ("ftok", "999"))

    def test_send_dry_run_without_creds_returns_false(self):
        self.assertFalse(notify.send("hello"))

    def test_send_calls_transport_with_creds(self):
        os.environ["ORCH_TG_TOKEN"] = "tok"
        os.environ["ORCH_TG_CHAT"] = "123"
        captured = {}

        def fake(url, payload):
            captured["url"] = url
            captured["payload"] = payload

        self.assertTrue(notify.send("hi", title="A needs you",
                                    transport=fake))
        self.assertIn("bottok/sendMessage", captured["url"])
        self.assertEqual(captured["payload"]["chat_id"], "123")
        self.assertIn("A needs you", captured["payload"]["text"])
        self.assertIn("hi", captured["payload"]["text"])


if __name__ == "__main__":
    unittest.main()
