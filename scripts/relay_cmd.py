#!/usr/bin/env python3
"""Quick relay command tool + bridge."""
import urllib.request, urllib.error, json, sys, os
from urllib.parse import quote
from pathlib import Path

RELAY_URL = os.environ.get("RELAY_URL", "http://114.212.122.10:8899")
TOKEN = os.environ.get("RELAY_TOKEN", "***")
STATE_FILE = Path.home() / ".hermes" / "relay_bridge_state.json"
ALL_AGENTS = ["bladerunner", "forest", "openclaw", "\u6811\u4e0a\u7684AI", "ubuntu", "homeclaw"]

def api(path, method="GET", data=None):
    url = f"{RELAY_URL}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"

if cmd == "poll":
    h = api("/health")
    print(json.dumps(h, ensure_ascii=False, indent=2))
elif cmd == "send":
    target = sys.argv[2]
    msg = " ".join(sys.argv[3:])
    r = api("/relay/send", "POST", {
        "from": "homeclaw",
        "to": target,
        "msg": msg
    })
    print(json.dumps(r, ensure_ascii=False))
elif cmd == "broadcast":
    msg = " ".join(sys.argv[2:])
    sender = os.environ.get("RELAY_FROM", "homeclaw")
    r = api("/relay/broadcast", "POST", {
        "from": sender,
        "msg": msg
    })
    print(json.dumps(r, ensure_ascii=False, indent=2))
elif cmd == "peek_all":
    for agent in ALL_AGENTS:
        r = api(f"/relay/peek/{quote(agent)}")
        msgs = r.get("messages", [])
        if msgs:
            print(f"\n=== {agent} queue ({len(msgs)}) ===")
            for m in msgs:
                print(f"  [{m['from']}] {m['msg']}")
elif cmd == "mymail":
    r = api("/relay/poll/homeclaw")
    msgs = r.get("messages", [])
    if msgs:
        print(f"\U0001f4ec {len(msgs)} messages for homeclaw:")
        for m in msgs:
            reply = f" (reply to: {m['reply_to']})" if m.get('reply_to') else ""
            print(f"  [{m['from']}] {m['msg']}{reply}")
    else:
        print("\U0001f4ed No messages")

elif cmd == "bridge":
    # Bridge mode: peek all, diff against state, print only new
    import time as _time
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except:
            state = {}
    last_seen = state.get("last_seen", {})

    new_total = 0
    for agent in ALL_AGENTS:
        r = api(f"/relay/peek/{quote(agent)}")
        msgs = r.get("messages", [])
        if not msgs:
            continue
        prev = last_seen.get(agent, 0)
        for m in msgs:
            # Extract numeric timestamp from message id
            mid_str = m.get("id", "")
            mid = 0
            try:
                mid = int(mid_str.split("-")[0]) if "-" in mid_str else int(mid_str)
            except:
                pass
            if mid > prev:
                reply = f" (re:{m['reply_to']})" if m.get('reply_to') else ""
                print(f"[{m['from']} \u2192 {agent}] {m['msg']}{reply}")
                new_total += 1
                if mid > last_seen.get(agent, 0):
                    last_seen[agent] = mid

    state["last_seen"] = last_seen
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False))
    if new_total == 0:
        pass  # silent when nothing new

elif cmd == "bridge_reset":
    STATE_FILE.unlink(missing_ok=True)
    print("Bridge state reset. Next poll will dump all.")
