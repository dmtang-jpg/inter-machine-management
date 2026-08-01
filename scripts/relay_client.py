#!/usr/bin/env python3
"""
Agent Relay Client v2.0 — Agent 端命令行工具
============================================
让每个 AI Agent 能方便地通过命令行收发消息。

用法:
  # 发送消息
  python3 relay_client.py send --from nightking --to forest --msg "What model?"

  # 轮询拉取（兼容旧方式）
  python3 relay_client.py poll --agent forest

  # SSE 实时接收（推荐）
  python3 relay_client.py listen --agent forest

  # 查看消息（不消费）
  python3 relay_client.py peek --agent nightking

  # 广播
  python3 relay_client.py broadcast --from nightking --msg "Meeting!"

  # 健康检查
  python3 relay_client.py health

环境变量:
  RELAY_URL   — relay 服务器地址（默认 http://localhost:8899）
  RELAY_TOKEN — 预共享认证密钥
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

RELAY_URL = os.environ.get('RELAY_URL', 'http://localhost:8899')
RELAY_TOKEN = os.environ.get('RELAY_TOKEN', '')


def _api(path, method='GET', data=None, stream=False):
    """调用 relay API"""
    url = f"{RELAY_URL}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    if RELAY_TOKEN:
        req.add_header('Authorization', f'Bearer {RELAY_TOKEN}')

    if data:
        req.data = json.dumps(data).encode('utf-8')

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        if stream:
            return resp  # 返回原始 response 供流式读取
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ HTTP {e.code}: {body[:300]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ 连接失败: {e.reason}", file=sys.stderr)
        sys.exit(1)


def cmd_send(args):
    """发送消息"""
    result = _api('/relay/send', method='POST', data={
        'from': args.from_agent,
        'to': args.to,
        'msg': args.msg,
        'reply_to': args.reply_to or None,
    })
    print(f"✅ 已发送 → {args.to}  (ID: {result.get('message_id', '?')})")


def cmd_poll(args):
    """轮询拉取消息"""
    params = [f'limit={args.limit}']
    if args.from_filter:
        params.append(f'from={args.from_filter}')
    path = f"/relay/poll/{args.agent}?{'&'.join(params)}"
    result = _api(path)

    msgs = result.get('messages', [])
    if not msgs:
        print("📭 没有新消息")
        return

    print(f"📬 {len(msgs)} 条消息:")
    for m in msgs:
        reply = f"  ↳ 回复: {m['reply_to']}" if m.get('reply_to') else ""
        print(f"  [{m['from']}] {m['msg']}{reply}")

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(msgs, ensure_ascii=False, indent=2))


def cmd_peek(args):
    """查看消息（不消费）"""
    result = _api(f'/relay/peek/{args.agent}')
    msgs = result.get('messages', [])
    if not msgs:
        print("📭 队列为空")
        return
    print(f"👀 {len(msgs)} 条待处理消息:")
    for m in msgs:
        print(f"  [{m['from']}] {m['msg']}")


def cmd_broadcast(args):
    """广播消息"""
    result = _api('/relay/broadcast', method='POST', data={
        'from': args.from_agent,
        'msg': args.msg,
    })
    print(f"📢 广播到 {result.get('count', 0)} 个 Agent: {', '.join(result.get('broadcast_to', []))}")


def cmd_health(args):
    """健康检查"""
    result = _api('/health')
    print(f"🏥 {result.get('server')}")
    print(f"   状态: {result.get('status')}")
    print(f"   认证: {'已启用' if result.get('auth_enabled') else '关闭'}")
    agents = result.get('agents_registered', [])
    queues = result.get('queue_sizes', {})
    print(f"   已知 Agent: {len(agents)} — {', '.join(agents) if agents else '(无)'}")
    print(f"   待处理消息: {result.get('total_pending', 0)}")
    if queues:
        for aid, size in sorted(queues.items()):
            print(f"     {aid}: {size}")


def cmd_listen(args):
    """
    SSE 实时接收模式（推荐）。
    保持长连接，新消息到达立即推送，逐条输出 JSON 到 stdout。
    """
    import ssl

    path = f"/relay/stream/{args.agent}"
    url = f"{RELAY_URL}{path}"
    req = urllib.request.Request(url)
    req.add_header('Accept', 'text/event-stream')
    req.add_header('Cache-Control', 'no-cache')
    if RELAY_TOKEN:
        req.add_header('Authorization', f'Bearer {RELAY_TOKEN}')

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print(f"👂 SSE 监听 {args.agent} (实时推送, Ctrl+C 停止)", file=sys.stderr)
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=3600)
        buffer = ""
        for chunk in iter(lambda: resp.read(4096), b''):
            buffer += chunk.decode('utf-8', errors='replace')
            while '\n\n' in buffer:
                block, buffer = buffer.split('\n\n', 1)
                for line in block.split('\n'):
                    if line.startswith('data: '):
                        data = line[6:]
                        try:
                            msg = json.loads(data)
                            print(json.dumps(msg, ensure_ascii=False))
                            sys.stdout.flush()
                        except json.JSONDecodeError:
                            pass
    except KeyboardInterrupt:
        print("\n👋 停止监听", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Agent Relay Client v2.0')
    sub = parser.add_subparsers(dest='command', required=True)

    # send
    p = sub.add_parser('send', help='发送消息')
    p.add_argument('--from', dest='from_agent', required=True)
    p.add_argument('--to', required=True)
    p.add_argument('--msg', required=True)
    p.add_argument('--reply-to')
    p.set_defaults(func=cmd_send)

    # poll
    p = sub.add_parser('poll', help='轮询拉取消息')
    p.add_argument('--agent', required=True)
    p.add_argument('--from', dest='from_filter')
    p.add_argument('--limit', type=int, default=50)
    p.add_argument('--json', action='store_true', help='输出 JSON')
    p.set_defaults(func=cmd_poll)

    # peek
    p = sub.add_parser('peek', help='查看消息（不消费）')
    p.add_argument('--agent', required=True)
    p.set_defaults(func=cmd_peek)

    # broadcast
    p = sub.add_parser('broadcast', help='广播到所有 Agent')
    p.add_argument('--from', dest='from_agent', required=True)
    p.add_argument('--msg', required=True)
    p.set_defaults(func=cmd_broadcast)

    # health
    p = sub.add_parser('health', help='健康检查')
    p.set_defaults(func=cmd_health)

    # listen (SSE)
    p = sub.add_parser('listen', help='SSE 实时监听（推荐）')
    p.add_argument('--agent', required=True)
    p.set_defaults(func=cmd_listen)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
