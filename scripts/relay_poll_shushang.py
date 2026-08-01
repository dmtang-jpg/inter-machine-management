#!/usr/bin/env python3
"""Poll relay for 树上的AI. Output only new messages — cron/watchdog friendly."""
import json, os, sys
import urllib.request, urllib.error

RELAY_URL = os.environ.get("RELAY_URL", "http://127.0.0.1:8899")
RELAY_TOKEN = os.environ.get("RELAY_TOKEN", "***")
STATE_FILE = os.path.expanduser("~/.hermes/relay_shushang_state.json")
AGENT = "树上的AI"

def api(path, method="GET", data=None):
    url = f"{RELAY_URL}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if RELAY_TOKEN:
        req.add_header("Authorization", f"Bearer {RELAY_TOKEN}")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

state = {}
try:
    with open(STATE_FILE) as f:
        state = json.load(f)
except:
    state = {"last_id": 0}

last_id = state.get("last_id", 0)

r = api(f"/relay/poll/{AGENT}?limit=20")
msgs = r.get("messages", [])
if not msgs:
    sys.exit(0)

new_msgs = []
new_max_id = last_id
for m in msgs:
    mid_str = m.get("id", "0")
    try:
        mid = int(mid_str.split("-")[0]) if "-" in mid_str else int(mid_str)
    except:
        mid = 0
    if mid > last_id:
        new_msgs.append(m)
        if mid > new_max_id:
            new_max_id = mid

if not new_msgs:
    sys.exit(0)

print(f"📬 树上的AI relay — {len(new_msgs)} 条新消息:")
for m in new_msgs:
    reply = f" (回复: {m['reply_to']})" if m.get("reply_to") else ""
    print(f"  [{m['from']}] {m['msg']}{reply}")

state["last_id"] = new_max_id
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
with open(STATE_FILE, "w") as f:
    json.dump(state, f)
