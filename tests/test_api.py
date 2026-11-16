"""Exercise actual HTTP handlers without requiring network access."""
import io
import json
import unittest
from server import Handler


def request(method, path, data=None):
    h = object.__new__(Handler)
    h.path = path
    body = json.dumps(data).encode() if data is not None else b""
    h.headers = {"Content-Length": str(len(body))}
    h.rfile = io.BytesIO(body)
    h.wfile = io.BytesIO()
    result = {}
    h.send_response = lambda status: result.update(status=status)
    h.send_header = lambda *args: None
    h.end_headers = lambda: None
    getattr(h, "do_" + method)()
    return result["status"], json.loads(h.wfile.getvalue())


class APITests(unittest.TestCase):
    def test_health(self):
        status, data = request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["engine"], "python")

    def test_compare_json_arrays(self):
        status, data = request("POST", "/api/compare", {"duration":30,"delays_s":[7,6,3]})
        self.assertEqual(status, 200)
        self.assertEqual(len(data), 3)
        self.assertTrue(all(x["status"] == "completed" for x in data.values()))

    def test_invalid_input(self):
        for data in ({"dt":0}, {"unknown":1}, [], {"setpoint_events":[[0,0.5,30]]}, {"duration":2,"dt":0.3}):
            self.assertEqual(request("POST", "/api/simulate", data)[0],400)

    def test_unknown_route(self):
        self.assertEqual(request("GET", "/missing")[0],404)

