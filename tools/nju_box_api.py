#!/usr/bin/env python3
"""NJU Box API - 南大云盘自动化管理脚本
Seafile Pro 13.0.20 兼容 API
"""
import requests
import re
import json
import sys
import os
from urllib.parse import quote as urlquote

# Configuration
BASE = "https://box.nju.edu.cn"
REPO_ID = "26fa0b5f-a7e0-429f-9d7f-8ecda8ef1a66"  # 新资料
LOGIN = "0410037"
PASSWORD = "njuee366"


class NjuBox:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # Self-signed cert
        self.login()
    
    def login(self):
        """登录并获取会话 — JWT 优先（可靠），Django session 兜底"""
        # Method 1: JWT token（不需要 CSRF，box 登录页改版/WAF 拦截时仍可用）
        try:
            resp = self.session.post(
                f"{BASE}/api2/auth-token/",
                json={"username": LOGIN, "password": PASSWORD},
                timeout=15,
            )
            if resp.status_code == 200:
                token = resp.json().get("token", "")
                if token:
                    self.session.headers["Authorization"] = f"Token {token}"
                    return True
        except Exception:
            pass
        # Method 2: Django session + CSRF（兜底）
        resp = self.session.get(f"{BASE}/accounts/login/", timeout=10)
        csrf = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', resp.text)
        if not csrf:
            raise RuntimeError("box login CSRF token not found; JWT auth also failed")
        self.session.post(f"{BASE}/accounts/login/", data={
            "csrfmiddlewaretoken": csrf.group(1),
            "login": LOGIN,
            "password": PASSWORD,
            "next": "/",
        }, headers={"Referer": f"{BASE}/accounts/login/"}, timeout=15)
        return True
    
    def _get_csrf_token(self):
        """从文件浏览器页面获取 session CSRF token"""
        resp = self.session.get(f"{BASE}/library/{REPO_ID}/", timeout=10)
        return re.search(r'csrfToken:\s*"([^"]*)"', resp.text).group(1)
    
    def create_directory(self, parent_path, folder_name):
        """创建文件夹
        Args:
            parent_path: 父目录路径 (如 "/")
            folder_name: 新文件夹名称
        Returns:
            str: 响应文本
        """
        token = self._get_csrf_token()
        # p 参数需要是完整的新目录路径 (URL 编码)
        if parent_path == "/":
            full_path = f"/{folder_name}"
        else:
            full_path = f"{parent_path}/{folder_name}"
        
        resp = self.session.post(
            f"{BASE}/api2/repos/{REPO_ID}/dir/?p={urlquote(full_path)}",
            data={"operation": "mkdir"},
            headers={
                "X-CSRFToken": token,
                "Referer": f"{BASE}/library/{REPO_ID}/",
            },
            timeout=10
        )
        return resp.text
    
    def list_directory(self, path="/"):
        """列出目录内容
        
        VERIFIED API (Seafile Pro 13.0.x):
        - Endpoint: GET /api2/repos/{repo_id}/dir/?p={quoted_path}
        - Returns a direct JSON list (NOT a dict with dirent_list key)
        - Each item has keys: type, name, id, mtime, permission, size
        """
        resp = self.session.get(
            f"{BASE}/api2/repos/{REPO_ID}/dir/?p={urlquote(path.lstrip('/') or '/')}",
            headers={"Accept": "application/json"},
            timeout=10
        )
        return resp.json()  # Returns list directly
    
    def delete_directory(self, dir_path):
        """删除文件夹
        Args:
            dir_path: 文件夹路径 (如 "/树上的AI")
        Returns:
            Response
        """
        resp = self.session.delete(
            f"{BASE}/api/v2.1/repos/{REPO_ID}/dir/?p={urlquote(dir_path)}",
            headers={"Accept": "application/json"},
            timeout=10
        )
        return resp
    
    def rename_directory(self, old_path, new_name):
        """重命名文件夹
        Args:
            old_path: 原路径
            new_name: 新名称
        Returns:
            Response
        """
        token = self._get_csrf_token()
        # Construct new path
        if old_path == "/":
            parent = "/"
        else:
            parent = old_path.rsplit("/", 1)[0] or "/"
        new_path = f"{parent}/{new_name}" if parent != "/" else f"/{new_name}"
        
        resp = self.session.post(
            f"{BASE}/api2/repos/{REPO_ID}/dir/?p={urlquote(old_path)}",
            data={"operation": "rename", "newname": new_name},
            headers={
                "X-CSRFToken": token,
                "Referer": f"{BASE}/library/{REPO_ID}/",
            },
            timeout=10
        )
        return resp
    
    def get_upload_link(self, target_path="/"):
        """获取上传链接
        Returns:
            str: upload_link URL
        """
        resp = self.session.get(
            f"{BASE}/api2/repos/{REPO_ID}/upload-link/?target_path={urlquote(target_path)}",
            timeout=10
        )
        return resp.text
    
    def print_tree(self, path="/"):
        """打印目录树形结构"""
        data = self.list_directory(path)
        dirs = sorted([d for d in data.get('dirent_list', []) if d['type'] == 'dir'], key=lambda x: x['name'])
        files = sorted([f for f in data.get('dirent_list', []) if f['type'] == 'file'], key=lambda x: x['name'])
        
        if path == "/":
            print("📁 ROOT/")
        else:
            print(f"📁 {path}/")
        
        for d in dirs:
            count = len(d.get('dirent_list', [])) if isinstance(d.get('dirent_list'), list) else "?"
            print(f"  ├── 📁 {d['name']}/")
        
        for i, f in enumerate(files):
            connector = "└── " if i == len(files) - 1 and not dirs else "├── "
            print(f"  {connector}📄 {f['name']} ({f.get('size', 0)} bytes)")
        
        if not dirs and not files:
            print("  (empty)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python nju_box_api.py [list|mkdir|rm|rename|upload] [args...]")
        print("  list [path]       - 列出目录")
        print("  mkdir name [path] - 创建文件夹")
        print("  rm path           - 删除文件夹")
        print("  rename old new    - 重命名")
        sys.exit(0)
    
    cmd = sys.argv[1]
    box = NjuBox()
    
    if cmd == "list":
        path = sys.argv[2] if len(sys.argv) > 2 else "/"
        data = box.list_directory(path)
        # API returns a flat list directly
        dirs = [d for d in data if d.get('type') == 'dir']
        files = [f for f in data if f.get('type') == 'file']
        print(f"\n目录 ({len(dirs)}):")
        for d in sorted(dirs, key=lambda x: x['name']):
            print(f"  📁 {d['name']}")
        print(f"文件 ({len(files)} - 前 10):")
        for f in sorted(files, key=lambda x: x['name'])[:10]:
            size_kb = f.get('size', 0) / 1024 if f.get('size', 0) else 0
            print(f"  📄 {f['name']} ({size_kb:.1f} KB)")
    
    elif cmd == "mkdir":
        if len(sys.argv) < 3:
            print("Usage: python nju_box_api.py mkdir <folder_name> [parent_path]")
            sys.exit(1)
        folder_name = sys.argv[2]
        parent_path = sys.argv[3] if len(sys.argv) > 3 else "/"
        result = box.create_directory(parent_path, folder_name)
        if '"success"' in result or result == "success":
            print(f"✅ 文件夹 '{folder_name}' 创建成功!")
        else:
            print(f"❌ 创建失败: {result}")
    
    elif cmd == "rm":
        if len(sys.argv) < 3:
            print("Usage: python nju_box_api.py rm <folder_path>")
            sys.exit(1)
        dir_path = sys.argv[2]
        resp = box.delete_directory(dir_path)
        if resp.status_code == 200:
            print(f"✅ 文件夹 '{dir_path}' 删除成功!")
        else:
            print(f"❌ 删除失败: {resp.text}")
    
    elif cmd == "rename":
        if len(sys.argv) < 4:
            print("Usage: python nju_box_api.py rename <old_path> <new_name>")
            sys.exit(1)
        old_path = sys.argv[2]
        new_name = sys.argv[3]
        resp = box.rename_directory(old_path, new_name)
        if resp.status_code == 200:
            print(f"✅ 重命名成功: {old_path} -> {new_name}")
        else:
            print(f"❌ 重命名失败: {resp.text}")
    
    elif cmd == "upload":
        if len(sys.argv) < 3:
            print("Usage: python nju_box_api.py upload <local_file> [remote_path]")
            sys.exit(1)
        local_file = sys.argv[2]
        remote_path = sys.argv[3] if len(sys.argv) > 3 else None
        
        # Use local filename if remote_path not specified
        if remote_path is None:
            filename = os.path.basename(local_file)
            parent_dir = "/"
        else:
            # If ends with / or is an existing directory path, treat as directory
            if remote_path.endswith('/') or remote_path.endswith('/.'):
                parent_dir = remote_path.rstrip('/')
                filename = os.path.basename(local_file)
            elif '/' in remote_path:
                parent_dir = remote_path.rsplit('/', 1)[0] or "/"
                filename = remote_path.rsplit('/', 1)[1] or os.path.basename(local_file)
            else:
                parent_dir = "/"
                filename = remote_path
        
        # Get upload link for the target directory
        link_text = box.session.get(
            f"{BASE}/api2/repos/{REPO_ID}/upload-link/?p={parent_dir}",
            timeout=10
        ).text.strip()
        upload_url = link_text.strip('"')
        
        if not upload_url:
            print("❌ 无法获取上传链接"); sys.exit(1)
        
        print(f"📤 正在上传 {local_file} -> {parent_dir}/{filename}")
        
        # Upload using proper multipart format:
        # POST to upload URL — filename comes from multipart file field name
        with open(local_file, 'rb') as fobj:
            resp = box.session.post(
                upload_url,
                files={'file': (filename, fobj, 'application/octet-stream')},
                data={'parent_dir': parent_dir},
                headers={"Referer": f"{BASE}/library/{REPO_ID}/"},
                timeout=60
            )
        
        if resp.status_code == 200:
            print(f"✅ 文件 '{local_file}' 上传成功! (hash: {resp.text.strip()})")
        else:
            print(f"❌ 上传失败: {resp.status_code} - {resp.text[:300]}")
    
    elif cmd == "tree":
        path = sys.argv[2] if len(sys.argv) > 2 else "/"
        box.print_tree(path)
    
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()
