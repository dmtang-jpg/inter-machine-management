#!/usr/bin/env python3
"""WPAD HTTP Server - serves proxy auto-config file for LAN devices.
   Listens on port 8080 (non-admin). Use portproxy for port 80 if needed.
"""
import http.server
import os
import sys
import mimetypes

PAC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wpad.dat")

class WPADHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(PAC_FILE), **kwargs)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/wpad.dat", "/proxy.pac"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            with open(PAC_FILE, "rb") as f:
                self.wfile.write(f.read())
        elif path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            idx = os.path.join(os.path.dirname(PAC_FILE), "index.html")
            if os.path.exists(idx):
                with open(idx, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"<h1>WPAD Server Running</h1>")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        print(f"[WPAD] {args[0]}")

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = http.server.HTTPServer(("0.0.0.0", port), WPADHandler)
    # 动态获取本机 IP（避免硬编码过期 IP）
    import socket
    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    print(f"[WPAD] Serving {PAC_FILE} on port {port}")
    print(f"[WPAD] PAC URL: http://{ip}:{port}/wpad.dat")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[WPAD] Stopped")

if __name__ == "__main__":
    main()
