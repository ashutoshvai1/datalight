"""Deterministic OpenAI-compatible fixture for synthetic browser tests only."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Do not log prompt bodies or credentials.

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"synthetic-model")

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        summary = json.loads(payload["messages"][-1]["content"])
        if "available_channel_ids" in summary:
            result = {
                "rule": {
                    "id": "proposal", "version": 1,
                    "channel_id": summary["available_channel_ids"][0],
                    "operator": "gt", "threshold": 80,
                    "minimum": None, "maximum": None, "effect": "fault",
                },
                "message": "",
            }
        elif summary.get("question") is not None:
            previous = len(summary.get("conversation", []))
            result = {
                "text": f"Synthetic answer with {previous} previous exchange(s). The supplied evidence records the batch decision; this does not establish a physical cause.",
                "evidence_ids": [summary["decision"]["evidence_id"]],
            }
        else:
            result = {"explanations": [
                {
                    "channel_id": profile["channel_id"],
                    "text": "Synthetic explanation: the initial reference is provisional. Forecast error describes past prediction performance.",
                    "evidence_ids": [profile["evidence_id"], profile["prediction_evidence_id"]],
                }
                for profile in summary["profiles"]
                if profile["channel_id"] in summary["target_channels"]
            ]}
        body = json.dumps({"choices": [{"message": {"content": json.dumps(result)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
