# 多机互通互管架构

> 最后更新: 2026-07-28 | 维护者: dmt | 待 @forest @openclaw AI 核查

## 拓扑总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        校园网 114.212.0.0/16                     │
│                                                                  │
│  ┌──────────────┐   WinRM:5985    ┌──────────────────────┐      │
│  │  办公Win11    │◄────────────────│                      │      │
│  │  .123.189     │   basic auth    │    Linux 114 (本机)   │      │
│  │  16GB / Win11 │                 │    114.212.122.10     │      │
│  └──────────────┘                 │    Hermes Agent       │      │
│                                    │    ~/manage.py        │      │
│  ┌──────────────┐   WinRM:5985    │                       │      │
│  │  煤球         │◄────────────────│    ┌───────────────┐  │      │
│  │  .234.221     │   ntlm auth     │    │ 核心服务:      │  │      │
│  │  8GB / Win11  │                 │    │ 8080 Gateway  │  │      │
│  │  Day8 VPN代理  │                 │    │ 8888 教学站   │  │      │
│  └──────────────┘                 │    │ 5005 Chat     │  │      │
│                                    │    │ 19999 Netdata │  │      │
│  ┌──────────────┐   SSH -R :9998  │    └───────────────┘  │      │
│  │  xhcl 服务器  │════════════════►│                       │      │
│  │  .236.180     │   反向隧道      │  ┌───────────────┐    │      │
│  │  WSL → Win11  │                │  │ 附加服务:      │    │      │
│  │  8080 Gateway │                │  │ 3000 WebUI    │    │      │
│  └──────────────┘                 │  │ 3001 one-api  │    │      │
│                                    │  │ 4096 opencode │    │      │
│  ┌──────────────┐   飞书群消息     │  │ 8001 adapters │    │      │
│  │  Forest       │◄═══════════════►│  │ 8188 ComfyUI  │    │      │
│  │  .233.97      │   (Agent中继)   │  │ 8089 ALD      │    │      │
│  │  WSL → Win11  │                │  │ 8890 PAC代理  │    │      │
│  │  CatMonitor   │                │  │ 8787 Bun      │    │      │
│  └──────────────┘                 │  └───────────────┘    │      │
│                                    │                       │      │
│  出国通道: 煤球 Day8 VPN :1088 ──► 外网                    │      │
│  代理配置: ~/.proxy_env (source by ~/.profile)             │
└─────────────────────────────────────────────────────────────────┘
```

## 机器清单

| 名称 | IP | OS | 管理通道 | 认证 | 统一密码 | 角色 |
|------|-----|-----|----------|------|:------:|------|
| **Linux 114** | 114.212.122.10 | Ubuntu 24.04 | — | — | njuee366 | 中枢/管理节点 |
| **办公Win11** | 114.212.123.189 | Win11 16GB | WinRM 5985 | basic / hermes_admin | njuee366 | 受管节点 |
| **煤球** | 114.212.234.221 | Win11 8GB | WinRM 5985 | ntlm / DM | njuee366 | 受管节点 + Day8 VPN |
| **xhcl 服务器** | 114.212.236.180 | WSL/Win11 | SSH -R :9998 | ed25519 key | — | API互通 |
| **Forest** | 114.212.233.97 | WSL/Win11 | 飞书Agent | — | — | CatMonitor |

---

## 管理方案一：WinRM 直管

**适用**: 办公Win11 + 煤球（Forest 待实施）

**原理**: Linux 通过 Python `winrm` 库远程执行 Windows 命令。

### 工具：`~/manage.py`

```python
#!/usr/bin/python3
"""用法: ~/manage.py <office|meiqiu|all> <command>"""
import sys, os
from winrm import Session

# WinRM 不走代理 — 自动清除
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

M = {
    "office": ("114.212.123.189:5985", "hermes_admin", "njuee366", "basic"),
    "meiqiu": ("114.212.234.221:5985", "DM", "njuee366", "ntlm"),
}

def run_one(target, cmd):
    host, user, pw, trans = M[target]
    s = Session(host, auth=(user, pw), transport=trans,
                server_cert_validation="ignore",
                read_timeout_sec=15, operation_timeout_sec=10)
    r = s.run_cmd(cmd)
    return r.std_out.decode("gbk", errors="replace").strip()

# 用法: ~/manage.py office "hostname"
#       ~/manage.py meiqiu "tasklist | findstr hermes"
#       ~/manage.py all "systeminfo"
```

**特点**:
- ✅ 低延迟（毫秒级响应）
- ✅ 批量执行（`manage.py all`）
- ✅ 自动清除代理环境变量
- ✅ 统一密码，认证协议差异（basic/ntlm）透明

**WinRM 配置**（Windows 端一次性操作）:
```powershell
Enable-PSRemoting -Force
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "114.212.122.10"
New-NetFirewallRule -Name "WinRM" -Direction Inbound -LocalPort 5985 -Protocol TCP -Action Allow
```

---

## 管理方案二：反向 SSH 隧道

**适用**: xhcl 服务器（Forest 同方案待实施）

**原理**: 服务器通过 SSH -R 将 Gateway API 端口反向映射到本机，绕过校园网端口封锁。

### 隧道方向

```
服务器 → 本机:  直连 http://114.212.122.10:8080          ✅ 8080 单向通
本机 → 服务器:  反向SSH隧道 127.0.0.1:9998 → 236.180:8080  ✅ 绕过封锁
```

### 建立隧道

```bash
# 服务器端执行（输密码不显示字符，盲打回车）
ssh -o StrictHostKeyChecking=no -R 9998:127.0.0.1:8080 dmt@114.212.122.10 -N
# -N 回车后"卡住"= 隧道已建立，正常现象
```

### 隧道自动重连（systemd service）

在服务器端创建 `~/.config/systemd/user/hermes-tunnel.service`：

```ini
[Unit]
Description=Hermes Reverse SSH Tunnel
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/ssh -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=no \
  -R 9998:127.0.0.1:8080 dmt@114.212.122.10 -N
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-tunnel
```

> 💡 先用 `ssh-keygen -t ed25519 && ssh-copy-id dmt@114.212.122.10` 免密，避免 systemd 无法输入密码。

### 本机验证

```bash
curl http://127.0.0.1:9998/health
# → {"status":"ok","platform":"hermes-agent","version":"0.17.0"}
```

---

## 管理方案三：飞书消息中继

**适用**: Forest（过渡方案）

**原理**: Forest 上运行 Hermes Agent，通过飞书群消息接收指令。

**特点**:
- ✅ 零入站端口需求
- ❌ 高延迟（消息往返秒级）
- ❌ Agent/飞书崩溃则失联，只能物理重启
- ❌ 群消息可能被 bot 忽略

**改进方案（待实施）**: Forest WSL 反向 SSH + WinRM，同方案二：

```bash
# Forest WSL 端 — WSL 宿主机 IP 在 /etc/resolv.conf 的 nameserver
ssh -o ServerAliveInterval=30 \
  -R 15985:$(grep nameserver /etc/resolv.conf | head -1 | awk '{print $2}'):5985 \
  dmt@114.212.122.10 -N
```

前提：Forest Windows 需开启 WinRM 并放行 5985（出站不受限，本地端口即可）。

---

## Gateway 跨机 API 互调

### 前置配置

两端 `~/.hermes/.env` 中设置相同密钥：
```bash
echo "API_SERVER_KEY=***" >> ~/.hermes/.env
```

`~/.hermes/config.yaml`：
```yaml
gateway:
  host: 0.0.0.0
  api_server:
    enabled: true
```

> ⚠️ API 始终绑在 Gateway 主端口（8080），不要单独设 `api_server.port`。

### 调用方式

| 方向 | URL | 通道 |
|------|-----|------|
| 本机 → 服务器 | `http://127.0.0.1:9998/v1/chat/completions` | SSH 反向隧道 |
| 服务器 → 本机 | `http://114.212.122.10:8080/v1/chat/completions` | 直连 |

```bash
# 示例：本机调服务器
curl -s -X POST http://127.0.0.1:9998/v1/chat/completions \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"检查状态"}]}'
```

### API Key 调试

| 症状 | 含义 |
|------|------|
| 401 瞬间返回 | Key 错误 |
| **超时（120s）** | Key 正确，模型推理中，**不要换 key** |

---

## Gateway 重启（busctl 绕过）

Gateway 拦截内部 `systemctl restart` 和 `kill -9`。**唯一方法：D-Bus 直调**。

```bash
# 1. 触发重启
busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 \
  org.freedesktop.systemd1.Manager RestartUnit "ss" \
  "hermes-gateway.service" "replace"

# 2. Gateway 忽略 SIGTERM，发 SIGKILL 强制结束
sleep 2
busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 \
  org.freedesktop.systemd1.Manager KillUnit "ssi" \
  "hermes-gateway.service" "main" 9

# 3. 等新 Gateway 起来
sleep 5
curl -s http://127.0.0.1:8080/health
```

---

## 出国代理

| 属性 | 值 |
|------|-----|
| 代理地址 | `http://114.212.234.221:1088` |
| 提供商 | Day8 VPN（运行在煤球上） |
| 配置文件 | `~/.proxy_env` |

```bash
# ~/.proxy_env（由 ~/.profile source）
export http_proxy="http://114.212.234.221:1088"
export https_proxy="http://114.212.234.221:1088"
export HTTP_PROXY="http://114.212.234.221:1088"
export HTTPS_PROXY="http://114.212.234.221:1088"
export no_proxy="api.deepseek.com,localhost,127.*,10.*,172.16.*,192.168.*,*.cn,*.baidu.com,*.aliyun.com,*.feishu.cn,114.212.*"
```

> Git SSH 22 直连 GitHub，不走代理。

---

## 自动化任务

| 任务 | 方式 | 时间 |
|------|------|------|
| Memory 清理 | cron (daily-memory-cleanup) | 每日 00:00 |
| HIP 缓存清理 | cron (hip-cache-cleanup) | 每日 04:00 |
| 大检查 | cron (daily-big-check) | 每日 02:00 |
| 隧道保活 | systemd (hermes-tunnel.service) | 服务器端自动重连 |
| Gateway 健康检查 | systemd timer | 每 5 分钟 |

---

## 网络限制

| 方向 | 状态 | 说明 |
|------|:----:|------|
| 122.10 → 236.180 :22 | ❌ | 超时，只能反向 SSH |
| 122.10 → 236.180 :8080 | ❌ | 反向不通 |
| 236.180 → 122.10 :8080 | ✅ | 8080 单向放行 |
| 122.10 → 233.97 (Forest) | ❌ | 100% 丢包 |
| 122.10 ↔ 123.189 :5985 | ✅ | 办公 WinRM |
| 122.10 ↔ 234.221 :5985 | ✅ | 煤球 WinRM |

---

## 已知问题 & Pitfalls

| 问题 | 影响 | 状态 |
|------|------|:----:|
| health-check 连续失效（set -e bug） | Gateway 无自动监控 | 待修复 |
| 18788 端口冲突（OpenClaw 占用） | 日志噪音，SSH 隧道无法用 18788 | 待解决 |
| Forest 频繁离线 | CatMonitor 不可靠 | 需物理操作 |
| 磁盘 81%（604G/787G） | 接近警戒线 | 监控中 |
| DeepSeek 流中断增多（16次/24h） | 长会话不稳定 | 需重启 Gateway |
| `api_server.port` 无效 | 永远绑 Gateway 主端口，另设无效 | 已知 |
| `config.yaml` 重复 `api_server` 段 | 前后不一致导致配置不生效 | 检查 `grep -n api_server` |
| `API_SERVER_KEY` 不重启不生效 | Gateway 仅启动时读 `.env` | 设完必须重启 |
| WSL 端口 NAT 暴露困难 | 反向 SSH 代替直连 | 已规避 |
| 飞书群聊 bot 可能不响应 | 不推荐作为主通道 | 已知 |

---

## 扩展计划

- [ ] Forest WSL → 反向 SSH + WinRM（同 xhcl 方案）
- [ ] 修复 health-check `set -e` 问题
- [ ] 解决 18788 端口冲突
- [ ] 磁盘清理

---

<!--
  各 Agent 核查栏：
  ✅ Linux 114 (Ubuntu) — 已确认，主持修订中
  ⬜ Forest — 待核查
  ⬜ OpenClaw AI — 待核查
  ⬜ xhcl 服务器 — 待核查
-->
