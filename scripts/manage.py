#!/usr/bin/env python3
"""煤球中央管理台 — manage.py <target|all> <action>"""

import sys, os, socket, time

PASSWORD = os.environ.get("WINRM_PASS", "")

MACHINES = {
    "office": {
        "ip": "114.212.123.189",
        "hostname": "DESKTOP-V09M1MB",
        "os": "Win11 Pro",
        "ram": "16GB",
        "access": {"type": "winrm", "user": "hermes_admin", "transport": "basic"},
        "services": {"hermes": "hermes.exe", "relay": "relay_client.py"},
    },
    "meiqiu": {
        "ip": "114.212.234.221",
        "hostname": "DESKTOP-97FQ8Q3",
        "os": "Win11",
        "ram": "8GB",
        "access": {"type": "winrm", "user": "DM", "transport": "ntlm"},
        "services": {"hermes": "hermes", "relay": "relay_client.py", "day8": "Day8.exe"},
    },
    "linux114": {
        "ip": "114.212.122.10",
        "hostname": "dmt-GTR-Pro",
        "os": "Ubuntu 24.04",
        "access": {"type": "ssh", "user": "dmt"},
        "services": {"relay": "relay_server.py", "gateway": "hermes"},
    },
    "forest": {
        "ip": "192.168.1.106",
        "hostname": "xhcl",
        "os": "WSL/Win11",
        "access": {"type": "ssh", "user": "dmt", "proxy": "ssh -p 15985 dmt@114.212.122.10"},
        "services": {"hermes": "hermes", "relay": "relay_client.py"},
    },
}

# ── actions ────────────────────────────────────────────────

def health(targets):
    """检查所有机器健康状态"""
    for name in targets or MACHINES:
        m = MACHINES[name]
        print(f"\n{'='*50}")
        print(f"  {name:12s} {m['hostname']:20s} {m['ip']}")
        print(f"{'='*50}")
        
        # Ping
        alive = ping(m["ip"], name)
        print(f"  {'✅' if alive else '❌'} Ping")
        if not alive:
            continue
        
        # Services
        for svc_name, pattern in m.get("services", {}).items():
            running = check_service(name, pattern)
            print(f"  {'✅' if running else '❌'} {svc_name}")
        
        # Disk
        if m["access"]["type"] == "winrm":
            disk = winrm(name, "wmic logicaldisk where \"DeviceID='C:'\" get FreeSpace,Size /format:list")
            if disk:
                print(f"  💾 C: {disk}")

def check_service(name, pattern):
    """Check if service is running"""
    m = MACHINES[name]
    if m["access"]["type"] == "winrm":
        out = winrm(name, f"tasklist | findstr \"{pattern}\"")
        return bool(out and pattern.lower() in out.lower())
    elif m["access"]["type"] == "ssh":
        out = ssh(name, f"pgrep -f \"{pattern}\"")
        return bool(out)
    return False

def restart(name):
    """重启指定机器的 Hermes"""
    if name not in MACHINES:
        print(f"未知机器: {name}")
        return
    
    m = MACHINES[name]
    print(f"重启 {name} Hermes...")
    
    if m["access"]["type"] == "winrm":
        out = winrm(name, "taskkill /F /IM hermes.exe 2>nul & timeout /t 2 >nul")
        out = winrm(name, "schtasks /run /tn GW_FIX 2>nul || schtasks /run /tn HermesGateway 2>nul")
        print(f"  结果: {out[:100] if out else '已触发重启任务'}")
    elif m["access"]["type"] == "ssh":
        out = ssh(name, "pkill -f 'hermes.gateway.run'; sleep 2; nohup ~/.hermes/bin/uv run hermes gateway run >/dev/null 2>&1 &")
        print(f"  结果: {'已重启' if out is not None else 'SSH失败'}")

def day8(action):
    """控制 Day8 VPN"""
    if action == "status":
        out = winrm("meiqiu", "powershell -File C:/Users/DM/Desktop/day8_manager.ps1 status")
        print(out)
    elif action == "restart":
        out = winrm("meiqiu", "powershell -File C:/Users/DM/Desktop/day8_manager.ps1 restart")
        print(out)

# ── transport helpers ──────────────────────────────────────

def ping(ip, name=None):
    # Forest uses reverse SSH tunnel on 122.10
    if name == "forest":
        return ssh("forest", "echo alive") is not None
    for port in [5985, 22]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            if s.connect_ex((ip, port)) == 0:
                s.close()
                return True
            s.close()
        except:
            pass
    return False

def ssh(name, cmd):
    m = MACHINES[name]
    # For forest, go through reverse tunnel
    import subprocess
    if name == "forest":
        full_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p 15985 dmt@114.212.122.10 \"{cmd}\""
    else:
        full_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {m['access']['user']}@{m['ip']} \"{cmd}\""
    try:
        r = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout.strip()
    except:
        return None

def winrm(name, cmd):
    m = MACHINES[name]
    acc = m["access"]
    for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:
        os.environ.pop(k, None)
    try:
        import winrm as wrm
        s = wrm.Session(f'{m["ip"]}:5985', auth=(acc["user"], PASSWORD), 
                         transport=acc["transport"], server_cert_validation="ignore",
                         read_timeout_sec=20, operation_timeout_sec=15)
        r = s.run_cmd(cmd)
        return r.std_out.decode('gbk', errors='replace').strip()
    except Exception as e:
        return str(e)[:100]

# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: manage.py health|restart <name>|day8 <status|restart>|all")
        print("目标: office, meiqiu, linux114, forest, all")
        sys.exit(1)

    action = sys.argv[1]
    
    if action == "health":
        health(sys.argv[2:] if len(sys.argv) > 2 else None)
    elif action == "restart":
        restart(sys.argv[2])
    elif action == "day8":
        day8(sys.argv[2] if len(sys.argv) > 2 else "status")
    elif action == "all":
        health(MACHINES.keys())
