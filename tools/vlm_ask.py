#!/usr/bin/env python3
"""
本地看图辅助模型客户端 (Qwen2.5-VL-3B, llama.cpp)
用法:
    python3 vlm_ask.py 图片.png [问题]
    python3 vlm_ask.py 图片.png                # 默认: 识别图中所有文字
    python3 vlm_ask.py 截图.png "这张图里有什么? 描述一下"
    python3 vlm_ask.py --screen "识别弹窗内容"   # 截屏后识别 (Linux, 需 scrot)
服务地址: http://<vlm主机>:8091 (OpenAI 兼容)
注意: 内置 trust_env=False, 不受 HTTP_PROXY 环境变量劫持
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

SERVER = "http://10.218.208.65:8091/v1/chat/completions"  # 本机 VLM 服务（内网 IP，同网段 agent 可直接访问）
DEFAULT_Q = "识别这张图片中的所有文字，逐行输出，不要遗漏，不要翻译。"


def img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def ask(image_path: str, question: str = DEFAULT_Q, max_tokens: int = 500,
        timeout: int = 180) -> str:
    payload = {
        "model": "qwen2.5-vl-3b",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{img_to_b64(image_path)}"}},
                {"type": "text", "text": question},
            ],
        }],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        SERVER, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    # 绕过环境变量代理: 用直接 opener
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    try:
        resp = json.loads(opener.open(req, timeout=timeout).read())
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"❌ 无法连接 VLM 服务 {SERVER}（{e.reason}）。"
            f"请确认服务在线: curl -s {SERVER.replace('/v1/chat/completions', '/health')}") from e
    except Exception as e:
        raise RuntimeError(f"❌ VLM 请求失败: {e}") from e
    dt = time.time() - t0
    text = resp["choices"][0]["message"]["content"]
    return f"[耗时 {dt:.1f}s]\n{text}"


def grab_screen(tmp_path: str) -> str:
    try:
        subprocess.run(["scrot", tmp_path], check=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        raise RuntimeError(f"❌ 截屏失败（scrot 不可用?）: {e}") from e
    return tmp_path


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    try:
        if args[0] == "--screen":
            question = args[1] if len(args) > 1 else DEFAULT_Q
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                shot = tf.name
            grab_screen(shot)
            print(f"[已截屏: {shot}]")
            print(ask(shot, question))
        else:
            img = args[0]
            if not os.path.exists(img):
                print(f"❌ 文件不存在: {img}", file=sys.stderr)
                sys.exit(1)
            question = args[1] if len(args) > 1 else DEFAULT_Q
            print(ask(img, question))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
