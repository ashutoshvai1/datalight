"""Deterministic OpenAI-compatible fixture for synthetic browser tests only."""

import json
import re
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
            # Test-only grammar, not a production rule extractor or canned domain answer.
            match = re.fullmatch(
                r"Flag (?:a )?fault if (c\d+) exceeds (\d+(?:\.\d+)?)",
                summary["request"],
                re.IGNORECASE,
            )
            result = {
                "rule": None,
                "message": "Synthetic fixture supports only explicit exceeds rules.",
            }
            if match and match[1] in summary["available_channel_ids"]:
                result = {
                    "rule": {
                        "id": "proposal",
                        "version": 1,
                        "channel_id": match[1],
                        "operator": "gt",
                        "threshold": float(match[2]),
                        "minimum": None,
                        "maximum": None,
                        "effect": "fault",
                    },
                    "message": "Synthetic test proposal; not a live model response.",
                }
        elif summary.get("question") is not None:
            previous = len(summary.get("conversation", []))
            result = {
                "text": f"Synthetic answer with {previous} previous exchange(s). The supplied evidence records the batch decision; this does not establish a physical cause.",
                "evidence_ids": [
                    summary["decision"]["evidence_id"],
                    *[
                        rule["evidence_id"]
                        for rule in summary["decision"].get("rule_evidence", [])
                    ],
                ],
            }
        else:
            result = {
                "explanations": [
                    {
                        "channel_id": profile["channel_id"],
                        "text": "Synthetic explanation: the initial reference is provisional. Forecast error describes past prediction performance.",
                        "evidence_ids": [
                            profile["evidence_id"],
                            profile["prediction_evidence_id"],
                        ],
                    }
                    for profile in summary["profiles"]
                    if profile["channel_id"] in summary["target_channels"]
                ]
            }
        body = json.dumps(
            {"choices": [{"message": {"content": json.dumps(result)}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
