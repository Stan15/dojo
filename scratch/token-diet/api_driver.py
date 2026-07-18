"""Clean ollama driver for measure.py batteries (scratch; never ships).

ollama 0.32.x's CLI (`ollama run`) writes its terminal word-rewrap rendering
into piped stdout — ANSI erase sequences plus re-printed word fragments land
INSIDE JSON string values and even double closing quotes, breaking balance
(discovered 2026-07-17: 48/64 "no JSON object found" on a model whose API
output is clean). The HTTP API returns the exact model text, matching the
clean semantics the 0.13.4 CLI had when the earlier baselines were collected.

Usage as a driver: python scratch/token-diet/api_driver.py <model> [--no-think]
Reads the prompt on stdin, prints the response (thinking text first when the
model emits it — whole-trace stdout parity with the old CLI).
"""
import json
import sys
import urllib.request

model = sys.argv[1]
body = {"model": model, "prompt": sys.stdin.read(), "stream": False}
if "--no-think" in sys.argv[2:]:
    body["think"] = False
req = urllib.request.Request(
    "http://localhost:11434/api/generate",
    json.dumps(body).encode("utf-8"),
    {"Content-Type": "application/json"},
)
resp = json.load(urllib.request.urlopen(req, timeout=1800))
out = resp.get("response", "")
if resp.get("thinking"):
    out = resp["thinking"] + "\n" + out
print(out)
