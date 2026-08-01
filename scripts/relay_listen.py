#!/usr/bin/env python3
"""SSE listener for agent relay - prints messages as they arrive."""
import urllib.request, urllib.error, json, sys, ssl, os

RELAY_URL = os.environ.get("RELAY_URL", "http://114.212.122.10:8899")
TOKEN = os.environ.get("RELAY_TOKEN", "***")
AGENT = sys.argv[1] if len(sys.argv) > 1 else "homeclaw"

url = f"{RELAY_URL}/relay/stream/{AGENT}"
req = urllib.request.Request(url)
req.add_header("Accept", "text/event-stream")
req.add_header("Cache-Control", "no-cache")
req.add_header("Authorization", f"Bearer {TOKEN}")

print(f"SSE listening as {AGENT}...", file=sys.stderr, flush=True)
try:
    resp = urllib.request.urlopen(req, timeout=300)
    buffer = ""
    for chunk in iter(lambda: resp.read(4096), b""):
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            for line in block.split("\n"):
                if line.startswith("data: "):
                    data = line[6:]
                    try:
                        msg = json.loads(data)
                        print(json.dumps(msg, ensure_ascii=False), flush=True)
                    except json.JSONDecodeError:
                        pass
except KeyboardInterrupt:
    print("\nStopped", file=sys.stderr)
