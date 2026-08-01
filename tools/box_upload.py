#!/usr/bin/env python3
"""Box 上传工具 — 已验证的完整流程 (2026-08-01)
用法:
    python3 box_upload.py <本地文件> <目标目录如 /公共 或 /树上的AI>
要点:
    - JWT 认证 (POST /api2/auth-token/)
    - upload-link 必须 GET (POST 会 405), 返回带引号的 URL 需 strip
    - upload-api 类型需要 parent_dir 参数
    - 绕代理 (trust_env=False), 否则 HTTP_PROXY 劫持导致断连
"""
import sys
import requests
import urllib3

urllib3.disable_warnings()

BASE = "https://box.nju.edu.cn"
REPO_ID = "26fa0b5f-a7e0-429f-9d7f-8ecda8ef1a66"  # 新资料
LOGIN = "0410037"
PASSWORD = "njuee366"


def upload(local_path: str, target_dir: str) -> str:
    s = requests.Session()
    s.trust_env = False  # 绕代理
    s.verify = False

    # 1. JWT 认证
    r = s.post(f"{BASE}/api2/auth-token/",
               json={"username": LOGIN, "password": PASSWORD}, timeout=15)
    r.raise_for_status()
    token = r.json()["token"]
    s.headers["Authorization"] = f"Token {token}"

    # 2. 拿上传链接 (GET + p=目标目录)
    r = s.get(f"{BASE}/api2/repos/{REPO_ID}/upload-link/?p={target_dir}", timeout=30)
    r.raise_for_status()
    upload_url = r.text.strip().strip('"')

    # 3. 上传 (带 parent_dir)
    fname = local_path.split("/")[-1]
    with open(local_path, "rb") as f:
        r = s.post(upload_url, files={"file": (fname, f)},
                   data={"parent_dir": target_dir}, timeout=300)
    r.raise_for_status()
    return r.text


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    result = upload(sys.argv[1], sys.argv[2])
    print(f"OK: {sys.argv[1]} -> {sys.argv[2]} | file_id={result[:40]}")
