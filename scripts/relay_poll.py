#!/usr/bin/env python3
"""Simple relay poll for homeclaw."""
import urllib.request, urllib.error, json, os

RELAY_URL = os.environ.get("RELAY_URL", "http://114.212.122.10:8899")
TOKEN = os.environ.get("RELAY_TOKEN", "")

url = f"{RELAY_URL}/relay/poll/homeclaw"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")

try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    msgs = data.get("messages", [])
    if msgs:
        print(f"📬 {len(msgs)} messages:")
        for m in msgs:
            reply = f" (reply to: {m['reply_to']})" if m.get('reply_to') else ""
            print(f"  [{m['from']}] {m['msg']}{reply}")
    else:
        print("📭 No messages for homeclaw")
except Exception as e:
    print(f"Error: {e}")
