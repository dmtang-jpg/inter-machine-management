#!/usr/bin/env python3
"""
Relay ↔ Feishu Bridge
Polls all agent queues, diffs against last-seen state, prints new messages.
State file: ~/.hermes/relay_bridge_state.json
"""
import urllib.request, urllib.error, json, os, sys, time
from pathlib import Path

RELAY_URL = os.environ.get("RELAY_URL", "http://114.212.122.10:8899")
TOKEN = os.environ.get("RELAY_TOKEN", "")
if not TOKEN:
    TOKEN = os.environ.get("TOKEN", "")
STATE_FILE = Path.home() / ".hermes" / "relay_bridge_state.json"
ALL_AGENTS = ["bladerunner", "forest", "openclaw", "树上的AI", "ubuntu"]

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

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

def peek_all():
    """Peek all agents' messages without consuming."""
    state = load_state()
    new_msgs = []
    seen = state.get("last_seen", {})

    for agent in ALL_AGENTS:
        r = api(f"/relay/peek/{agent}")
        msgs = r.get("messages", [])
        last_id = seen.get(agent, 0)

        for m in msgs:
            mid = int(m["id"].split("-")[0]) if "-" in m.get("id", "") else 0
            if mid > last_id:
                new_msgs.append({
                    "agent": agent,
                    "from": m["from"],
                    "msg": m["msg"],
                    "id": m["id"],
                    "timestamp": mid,
                    "reply_to": m.get("reply_to"),
                })
                if mid > seen.get(agent, 0):
                    seen[agent] = mid

    state["last_seen"] = seen
    save_state(state)
    return new_msgs

def cmd_peek_all():
    new = peek_all()
    if new:
        for m in new:
            reply = f" (回复{m['reply_to']})" if m.get("reply_to") else ""
            print(f"[{m['from']} → {m['agent']}] {m['msg']}{reply}")
    # else: silent - nothing new

def cmd_send(target, msg):
    r = api("/relay/send", "POST", {
        "from": "homeclaw",
        "to": target,
        "msg": msg
    })
    if r.get("status") == "ok":
        print(f"✅ 已发送 → {target}")
    else:
        print(f"❌ 发送失败: {r}")

def cmd_reset():
    """Reset seen state to capture all current messages."""
    STATE_FILE.unlink(missing_ok=True)
    print("🔄 State reset. Next poll will capture all queued messages.")

def cmd_status():
    h = api("/health")
    print(f"🏥 Relay: {h.get('status')}")
    print(f"   Pending: {h.get('total_pending')}")
    for aid, size in sorted(h.get("queue_sizes", {}).items()):
        print(f"   {aid}: {size}")

def cmd_help():
    print("""Relay Bridge commands:
  python relay_bridge.py peek     — check for new messages (prints only new)
  python relay_bridge.py status   — relay health + queue sizes
  python relay_bridge.py send <agent> <msg>  — send message
  python relay_bridge.py reset    — reset seen state
  python relay_bridge.py dump     — dump ALL messages (with state tracking)
""")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "peek"
    if cmd == "peek":
        cmd_peek_all()
    elif cmd == "dump":
        cmd_reset()
        cmd_peek_all()
    elif cmd == "status":
        cmd_status()
    elif cmd == "send":
        if len(sys.argv) < 4:
            print("Usage: relay_bridge.py send <agent> <msg>")
            sys.exit(1)
        cmd_send(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "reset":
        cmd_reset()
    else:
        cmd_help()
