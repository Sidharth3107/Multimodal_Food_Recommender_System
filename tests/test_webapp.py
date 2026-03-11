from __future__ import annotations

import json
import threading
import unittest
from urllib.request import Request, urlopen

from webapp.server import NutriguardHTTPServer, NutriguardWebState


class WebAppTests(unittest.TestCase):
    def test_health_showcase_and_analyze_endpoints(self) -> None:
        server = NutriguardHTTPServer(("127.0.0.1", 0), NutriguardWebState())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        base_url = f"http://{host}:{port}"
        try:
            health = json.loads(urlopen(f"{base_url}/api/health", timeout=5).read().decode("utf-8"))
            showcase = json.loads(urlopen(f"{base_url}/api/showcase", timeout=5).read().decode("utf-8"))

            payload = {
                "profile": {
                    "name": "Alex",
                    "allergies": ["milk"],
                    "diet": "vegan",
                    "avoid_ingredients": ["gelatin"],
                    "strict_mode": True,
                    "health_goals": ["lower sugar"],
                },
                "barcode": "1003",
                "dataset": "tests/data/sample_openfoodfacts.tsv",
            }
            request = Request(
                f"{base_url}/api/analyze",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            analysis = json.loads(urlopen(request, timeout=15).read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertTrue(health["ok"])
        self.assertIn("cases", showcase)
        self.assertGreaterEqual(len(showcase["cases"]), 1)
        self.assertIn("result", analysis)
        self.assertEqual(analysis["result"]["status"], "safe")
        self.assertIn("report_href", analysis)


if __name__ == "__main__":
    unittest.main()
