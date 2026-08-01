# ============================================================
#  Win10 一键接入管理网络 + 安装 Hermes (deepseek-v4-flash)
#  运行方式: 右键"以管理员身份运行" 或 PowerShell 里执行
#  (本脚本由 煤球 Hermes 自动生成)
# ============================================================

# ---- 0. 自提管理员权限 ----
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
Write-Host "=== [0/9] 已获得管理员权限 ===" -ForegroundColor Green

# ---- 1. 开启 WinRM (远程管理) ----
Write-Host "=== [1/9] 配置 WinRM ===" -ForegroundColor Green
try {
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "LocalAccountTokenFilterPolicy" -Value 1 -Type DWord -Force
    # 注意：winrm quickconfig 的静默参数是 -q，不是 -quiet
    winrm quickconfig -q 2>$null | Out-Null
    Set-Service WinRM -StartupType Automatic
    Start-Service WinRM -ErrorAction SilentlyContinue
    Set-Item WSMan:\localhost\Client\TrustedHosts -Value "*" -Force 2>$null
    # pywinrm/basic 认证必须：开启 Basic 认证 + 允许未加密传输
    winrm set winrm/config/service/auth @{Basic="true"} 2>$null | Out-Null
    winrm set winrm/config/service @{AllowUnencrypted="true"} 2>$null | Out-Null
    winrm set winrm/config/service @{MaxEnvelopeSizekb="512"} 2>$null | Out-Null
    New-NetFirewallRule -DisplayName "WinRM HTTP" -Direction Inbound -Protocol TCP -LocalPort 5985 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    Write-Host "  [OK] WinRM 已启用 (5985)" -ForegroundColor Green
} catch { Write-Host "  [WARN] WinRM: $_" -ForegroundColor Yellow }

# ---- 2. 开启远程桌面 (可选) ----
Write-Host "=== [2/9] 开启远程桌面 ===" -ForegroundColor Green
try {
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0 -Type DWord -Force
    New-NetFirewallRule -DisplayName "RDP" -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    Write-Host "  [OK] RDP 已开启 (3389)" -ForegroundColor Green
} catch { Write-Host "  [WARN] RDP: $_" -ForegroundColor Yellow }

# ---- 3. 开启 OpenSSH Server (可选) ----
Write-Host "=== [3/9] 开启 OpenSSH Server ===" -ForegroundColor Green
try {
    # 注意：Get-WindowsCapability 可能返回数组，需遍历取第一个可安装项
    $caps = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
    $sshCap = $caps | Where-Object { $_.State -ne "Installed" } | Select-Object -First 1
    if ($sshCap) {
        Add-WindowsCapability -Online -Name $sshCap.Name | Out-Null
    }
    Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
    Start-Service sshd -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName "SSH" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    Write-Host "  [OK] OpenSSH 已开启 (22)" -ForegroundColor Green
} catch { Write-Host "  [WARN] SSH: $_" -ForegroundColor Yellow }

# ---- 4. 开启网络发现 + 防火墙共享 ----
Write-Host "=== [4/9] 网络发现 ===" -ForegroundColor Green
try {
    # 注意：中文系统上 netsh 组名是本地化的（"网络发现"/"文件和打印机共享"），
    # 用英文组名会失败。改用 PowerShell 直接放行端口，与语言无关。
    New-NetFirewallRule -DisplayName "SMB 445" -Direction Inbound -Protocol TCP -LocalPort 445 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "NetBIOS 139" -Direction Inbound -Protocol TCP -LocalPort 139 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "RPC 135" -Direction Inbound -Protocol TCP -LocalPort 135 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    # 网络发现规则组（尝试中英文，忽略失败）
    netsh advfirewall firewall set rule group="Network Discovery" new enable=Yes 2>$null | Out-Null
    netsh advfirewall firewall set rule group="网络发现" new enable=Yes 2>$null | Out-Null
    Write-Host "  [OK] 网络发现已开启" -ForegroundColor Green
} catch { Write-Host "  [WARN] 网络发现: $_" -ForegroundColor Yellow }

# ---- 5. 系统代理 -> 煤球 Day8 (国内直连) ----
Write-Host "=== [5/9] 配置系统代理 ===" -ForegroundColor Green
try {
    $path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    Set-ItemProperty -Path $path -Name ProxyServer -Value "114.212.234.221:1088"
    Set-ItemProperty -Path $path -Name ProxyOverride -Value "<local>;127.0.0.1;::1;10.0.0.0/8;172.16.0.0/12;192.168.0.0/16;*.cn;*.edu.cn;*.nju.edu.cn;*.baidu.com;*.aliyun.com;*.feishu.cn;114.212.*;api.deepseek.com"
    Set-ItemProperty -Path $path -Name ProxyEnable -Value 1
    Write-Host "  [OK] 系统代理 -> 114.212.234.221:1088" -ForegroundColor Green
} catch { Write-Host "  [WARN] 代理: $_" -ForegroundColor Yellow }

# ---- 6. 安装 Python 3.12 (如缺失) ----
Write-Host "=== [6/9] 检查 Python ===" -ForegroundColor Green
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "  未检测到 Python，用 winget 安装..." -ForegroundColor Yellow
    try {
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements 2>$null | Out-Null
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        Write-Host "  [OK] Python 3.12 已安装" -ForegroundColor Green
    } catch { Write-Host "  [FAIL] Python 安装失败: $_" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "  [OK] Python 已存在: $($py.Source)" -ForegroundColor Green
}

# ---- 7. 安装 Hermes ----
Write-Host "=== [7/9] 安装 Hermes ===" -ForegroundColor Green
try {
    # 注意：pip 不读 Windows 系统代理！必须显式指定 --proxy 或设置环境变量
    $env:HTTP_PROXY = "http://114.212.234.221:1088"
    $env:HTTPS_PROXY = "http://114.212.234.221:1088"
    $env:NO_PROXY = "localhost,.cn,.edu.cn,.nju.edu.cn,114.212.0.0/16,api.deepseek.com"
    python -m pip install --upgrade pip 2>$null | Out-Null
    python -m pip install hermes-agent 2>&1 | Select-Object -Last 3
    Write-Host "  [OK] hermes-agent 已安装" -ForegroundColor Green
} catch { Write-Host "  [FAIL] Hermes 安装失败: $_" -ForegroundColor Red }

# ---- 8. 配置 Hermes: deepseek-v4-flash ----
Write-Host "=== [8/9] 配置 Hermes 模型 ===" -ForegroundColor Green
try {
    # 确保 hermes 命令可用
    $hermesCmd = Get-Command hermes -ErrorAction SilentlyContinue
    if (-not $hermesCmd) {
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        $hermesCmd = Get-Command hermes -ErrorAction SilentlyContinue
    }
    if ($hermesCmd) {
        hermes config set model.default deepseek-v4-flash
        hermes config set model.provider deepseek
        Write-Host "  [OK] 模型 = deepseek-v4-flash (deepseek)" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] hermes 命令未找到，跳过模型配置" -ForegroundColor Yellow
    }
} catch { Write-Host "  [WARN] 模型配置: $_" -ForegroundColor Yellow }

# ---- 9. 写入 API Key + 环境文件 ----
Write-Host "=== [9/9] 写入 API Key 与代理环境 ===" -ForegroundColor Green
try {
    # DeepSeek API Key (部署时注入)
    $hermesHome = "$env:LOCALAPPDATA\hermes"
    if (-not (Test-Path $hermesHome)) { New-Item -ItemType Directory -Path $hermesHome -Force | Out-Null }
    $envFile = Join-Path $hermesHome ".env"
    $envContent = @"
DEEPSEEK_API_KEY=DEEPSEEK_KEY_PLACEHOLDER
"@
    [System.IO.File]::WriteAllText($envFile, $envContent, [System.Text.Encoding]::UTF8)

    # 代理环境文件 (git-bash / WSL 用)
    $proxyEnv = Join-Path $env:USERPROFILE ".proxy_env"
    $proxyContent = @"
# Day8 VPN proxy -> meiqiu (overseas only)
export http_proxy="http://114.212.234.221:1088"
export https_proxy="http://114.212.234.221:1088"
export HTTP_PROXY="http://114.212.234.221:1088"
export HTTPS_PROXY="http://114.212.234.221:1088"
export no_proxy="localhost,.local,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,.cn,.edu.cn,.nju.edu.cn,.baidu.com,.aliyun.com,.feishu.cn,114.212.0.0/16,api.deepseek.com"
export NO_PROXY="`$no_proxy"
"@
    [System.IO.File]::WriteAllText($proxyEnv, $proxyContent, [System.Text.Encoding]::ASCII)
    Write-Host "  [OK] .env 与 .proxy_env 已写入" -ForegroundColor Green
} catch { Write-Host "  [WARN] 写文件: $_" -ForegroundColor Yellow }

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " 部署完成！" -ForegroundColor Green
Write-Host " 本机 IP 查询: ipconfig" -ForegroundColor Cyan
Write-Host " 管理入口: WinRM 5985 / SSH 22 / RDP 3389" -ForegroundColor Cyan
Write-Host " Hermes: deepseek-v4-flash" -ForegroundColor Cyan
Write-Host " 代理: 114.212.234.221:1088 (国内直连)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "按回车退出"
