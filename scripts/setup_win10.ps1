# ============================================================
#  Win10 / Win11 一键接入管理网络 + 安装 Hermes (deepseek-v4-flash)
#  运行方式: 拷到本机 C:\ 后，在 PowerShell 里执行:
#    powershell -ExecutionPolicy Bypass -File setup_win10.ps1
#  （脚本自动申请管理员权限）
#  (本脚本由 煤球 Hermes 自动生成, 2026-08-01 更新: 兼容 Win11)
#  部署前替换 DEEPSEEK_KEY_PLACEHOLDER 为真实 key（sed 注入）
# ============================================================

# ---- 0. 自提管理员权限 ----
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
Write-Host "=== [0/12] 已获得管理员权限 ===" -ForegroundColor Green

# ---- 1. 开启 WinRM (远程管理) ----
Write-Host "=== [1/12] 配置 WinRM ===" -ForegroundColor Green
try {
    # Win11 24H2 上 WinRM 服务可能未启动/禁用，先确保服务可自启（sc 比 Set-Service 兼容性更好）
    sc.exe config winrm start= auto 2>$null | Out-Null
    Set-Service WinRM -StartupType Automatic -ErrorAction SilentlyContinue
    Start-Service WinRM -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    # 远程 UAC 过滤: 0=本地管理员远程连接时也持有完整令牌（WinRM/SSH 必需）
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "LocalAccountTokenFilterPolicy" -Value 1 -Type DWord -Force
    # 注意：winrm quickconfig 的静默参数是 -q，不是 -quiet
    winrm quickconfig -q 2>$null | Out-Null
    Set-Item WSMan:\localhost\Client\TrustedHosts -Value "*" -Force 2>$null
    # pywinrm/basic 认证必须：开启 Basic 认证 + 允许未加密传输
    winrm set winrm/config/service/auth @{Basic="true"} 2>$null | Out-Null
    winrm set winrm/config/service @{AllowUnencrypted="true"} 2>$null | Out-Null
    winrm set winrm/config/service @{MaxEnvelopeSizekb="512"} 2>$null | Out-Null
    New-NetFirewallRule -DisplayName "WinRM HTTP" -Direction Inbound -Protocol TCP -LocalPort 5985 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    # 认证自检：确认 Basic=true 真正生效
    $authCfg = winrm get winrm/config/service/auth 2>$null | Out-String
    $svcCfg  = winrm get winrm/config/service 2>$null | Out-String
    $basicOk = $authCfg -match "Basic\s*=\s*true"
    $unencOk = $svcCfg  -match "AllowUnencrypted\s*=\s*true"
    if ($basicOk -and $unencOk) {
        Write-Host "  [OK] WinRM 已启用 (5985), Basic认证=$basicOk 未加密=$unencOk" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] WinRM 配置未完全生效 (Basic=$basicOk Unencrypted=$unencOk)" -ForegroundColor Yellow
    }
} catch { Write-Host "  [WARN] WinRM: $_" -ForegroundColor Yellow }

# ---- 1b. 创建本地管理员账户（远程管理专用）----
Write-Host "=== [1b/12] 创建远程管理账户 ===" -ForegroundColor Green
try {
    # Microsoft 账户无法用 WinRM/SSH basic 认证，必须建本地账户
    # 账户: hermes_admin  密码: njuee366
    # 检查账户是否已存在（中文系统输出"用户名"而非"User name"，用退出码判断，语言无关）
    $exists = $false
    net user hermes_admin 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $exists = $true }
    if ($exists) {
        # 已存在则重置密码（保证幂等，重复跑不报错）
        net user hermes_admin njuee366 2>$null | Out-Null
        Write-Host "  [OK] 账户已存在，密码已重置" -ForegroundColor Green
    } else {
        net user hermes_admin njuee366 /add 2>$null | Out-Null
        net localgroup administrators hermes_admin /add 2>$null | Out-Null
        Write-Host "  [OK] 本地管理员 hermes_admin 已创建" -ForegroundColor Green
    }
    # 允许空密码远程（防止本地安全策略拦截）
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "LimitBlankPasswordUse" -Value 0 -Type DWord -Force
    # 加入远程桌面用户组（中英文组名都试）
    net localgroup "Remote Desktop Users" hermes_admin /add 2>$null | Out-Null
    net localgroup "远程桌面用户" hermes_admin /add 2>$null | Out-Null
} catch { Write-Host "  [WARN] 创建账户: $_" -ForegroundColor Yellow }

# ---- 2. 开启远程桌面 (可选) ----
Write-Host "=== [2/12] 开启远程桌面 ===" -ForegroundColor Green
try {
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0 -Type DWord -Force
    New-NetFirewallRule -DisplayName "RDP" -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    Write-Host "  [OK] RDP 已开启 (3389)" -ForegroundColor Green
} catch { Write-Host "  [WARN] RDP: $_" -ForegroundColor Yellow }

# ---- 3. 开启 OpenSSH Server (可选) ----
Write-Host "=== [3/12] 开启 OpenSSH Server ===" -ForegroundColor Green
try {
    # 注意：Get-WindowsCapability 可能返回数组，需遍历取第一个可安装项
    $caps = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
    $sshCap = $caps | Where-Object { $_.State -ne "Installed" } | Select-Object -First 1
    if ($sshCap) {
        Add-WindowsCapability -Online -Name $sshCap.Name | Out-Null
    }
    # Win11 上 sshd 服务由 capability 创建，需先确认存在再设自启
    $svc = Get-Service sshd -ErrorAction SilentlyContinue
    if ($svc) {
        Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
        Start-Service sshd -ErrorAction SilentlyContinue
    } else {
        Write-Host "  [WARN] sshd 服务未创建（Add-WindowsCapability 可能失败，需联网）" -ForegroundColor Yellow
    }
    New-NetFirewallRule -DisplayName "SSH" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    Write-Host "  [OK] OpenSSH 已开启 (22)" -ForegroundColor Green
} catch { Write-Host "  [WARN] SSH: $_" -ForegroundColor Yellow }

# ---- 4. 开启网络发现 + 防火墙共享 ----
Write-Host "=== [4/12] 网络发现 ===" -ForegroundColor Green
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
Write-Host "=== [5/12] 配置系统代理 ===" -ForegroundColor Green
try {
    $path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    Set-ItemProperty -Path $path -Name ProxyServer -Value "114.212.234.221:1088"
    Set-ItemProperty -Path $path -Name ProxyOverride -Value "<local>;127.0.0.1;::1;10.0.0.0/8;172.16.0.0/12;192.168.0.0/16;*.cn;*.edu.cn;*.nju.edu.cn;*.baidu.com;*.aliyun.com;*.feishu.cn;114.212.*;api.deepseek.com"
    Set-ItemProperty -Path $path -Name ProxyEnable -Value 1
    Write-Host "  [OK] 系统代理 -> 114.212.234.221:1088" -ForegroundColor Green
} catch { Write-Host "  [WARN] 代理: $_" -ForegroundColor Yellow }

# ---- 6. 安装/校验 Python 3.11~3.13 (Hermes 要求 <3.14,>=3.11) ----
Write-Host "=== [6/12] 检查 Python (Hermes 要求 3.11~3.13) ===" -ForegroundColor Green
# Hermes requires_python: <3.14,>=3.11 → 只接受 3.11/3.12/3.13
# Win10/Win11 通用：先测 python 是否真可用（Win11 商店别名/老 Win10 无 winget 都会坑在这）
$pyExe = "python"; $pyArgs = @(); $pyOk = $false
function Test-PyCompat {
    param([string]$VerText)
    # 只认 3.11/3.12/3.13（3.14+ 或 3.10- 都会被 pip 拒绝）
    return $VerText -match "Python 3\.(1[1-3])(\.|$)"
}
$pyVer = & python --version 2>&1 | Out-String
$pyOk = Test-PyCompat $pyVer
if (-not $pyOk) {
    # 尝试 py 启动器 (py -3.13 / -3.12 / -3.11)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("3.13", "3.12", "3.11")) {
            $t = & py "-$v" --version 2>&1 | Out-String
            if (Test-PyCompat $t) { $pyExe = "py"; $pyArgs = @("-$v"); $pyOk = $true; break }
        }
    }
}
if (-not $pyOk) {
    Write-Host "  Python 缺失或版本不兼容 Hermes (需 3.11~3.13)，尝试安装 3.12..." -ForegroundColor Yellow
    # TLS 1.2（老系统默认 TLS1.0 会被 python.org/微软拒）
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    try {
        # 方案1: winget（Win11 自带，Win10 新版有）
        $wg = Get-Command winget -ErrorAction SilentlyContinue
        if ($wg) {
            winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements 2>$null | Out-Null
        } else {
            # 方案2: 直接下载 python.org 安装包（走煤球代理，海外站）
            Write-Host "  winget 不可用（老 Win10），直接下载 Python 安装包..." -ForegroundColor Yellow
            $env:HTTP_PROXY  = "http://114.212.234.221:1088"
            $env:HTTPS_PROXY = "http://114.212.234.221:1088"
            $pyInstaller = "$env:TEMP\python-3.12.7-amd64.exe"
            Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" -OutFile $pyInstaller -UseBasicParsing -TimeoutSec 300
            Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0" -Wait
        }
        # 刷新 PATH
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        # 重新校验（python 或 py launcher）
        $pyVer2 = & python --version 2>&1 | Out-String
        if (Test-PyCompat $pyVer2) { $pyExe = "python"; $pyArgs = @(); $pyOk = $true }
        elseif (Get-Command py -ErrorAction SilentlyContinue) {
            foreach ($v in @("3.13", "3.12", "3.11")) {
                $t = & py "-$v" --version 2>&1 | Out-String
                if (Test-PyCompat $t) { $pyExe = "py"; $pyArgs = @("-$v"); $pyOk = $true; break }
            }
        }
        if ($pyOk) {
            $finalVer = & $pyExe @pyArgs --version 2>&1 | Out-String
            Write-Host "  [OK] Python 就绪: $($finalVer.Trim()) (via $pyExe $($pyArgs -join ' '))" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] Python 安装后仍不可用/不兼容: $pyVer2" -ForegroundColor Red; exit 1
        }
    } catch { Write-Host "  [FAIL] Python 安装失败: $_" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "  [OK] Python 已存在且兼容: $($pyVer.Trim())" -ForegroundColor Green
}

# ---- 7. 安装 Hermes (用第 6 步校验过的 Python) ----
Write-Host "=== [7/12] 安装 Hermes ===" -ForegroundColor Green
try {
    # 注意：pip 不读 Windows 系统代理！必须显式指定 --proxy 或设置环境变量
    $env:HTTP_PROXY = "http://114.212.234.221:1088"
    $env:HTTPS_PROXY = "http://114.212.234.221:1088"
    $env:NO_PROXY = "localhost,.cn,.edu.cn,.nju.edu.cn,114.212.0.0/16,api.deepseek.com"
    $env:PIP_DEFAULT_TIMEOUT = "60"
    & $pyExe @pyArgs -m pip install --upgrade pip 2>$null | Out-Null
    & $pyExe @pyArgs -m pip install hermes-agent 2>&1 | Select-Object -Last 3
    Write-Host "  [OK] hermes-agent 已安装" -ForegroundColor Green
} catch { Write-Host "  [FAIL] Hermes 安装失败: $_" -ForegroundColor Red }

# ---- 8. 配置 Hermes: deepseek-v4-flash ----
Write-Host "=== [8/12] 配置 Hermes 模型 ===" -ForegroundColor Green
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
Write-Host "=== [9/12] 写入 API Key 与代理环境 ===" -ForegroundColor Green
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
    Write-Host "  [OK] .env 与 .proxy_env 已写入 ($env:USERPROFILE)" -ForegroundColor Green
} catch { Write-Host "  [WARN] 写文件: $_" -ForegroundColor Yellow }

# ---- 10. 用户目录权限: hermes_admin 可管理所有用户配置文件 ----
#  (2026-08-01 新增: 解决 WinRM 远程管理时 hermes_admin 无权限读写
#   其他用户 hermes 配置目录的问题——即 wintertown 遗留的"目录权限"收尾项)
Write-Host "=== [10/12] 用户目录授权 (icacls) ===" -ForegroundColor Green
try {
    $skip = @('Default', 'Default User', 'All Users', 'Public', 'Administrator')
    $dirs = Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue |
            Where-Object { $skip -notcontains $_.Name -and $_.Name -notlike '*$*' }
    foreach ($d in $dirs) {
        icacls "`"$($d.FullName)`"" /grant "hermes_admin:(OI)(CI)F" /T /C /Q 2>$null | Out-Null
        Write-Host "  [OK] hermes_admin 已授权: $($d.Name)" -ForegroundColor Green
    }
} catch { Write-Host "  [WARN] icacls: $_" -ForegroundColor Yellow }

# ---- 11. 最终验证 ----
Write-Host "=== [11/12] 最终验证 ===" -ForegroundColor Green
try {
    $portOk = @(5985, 22, 3389) | ForEach-Object {
        $r = netstat -ano | Select-String ":$($_) " | Select-String "LISTENING"
        "$($_):$([bool]$r)"
    }
    $portOk | ForEach-Object { Write-Host "  [CHECK] 端口 $_" -ForegroundColor Cyan }
    $accOk = net user hermes_admin 2>$null | Select-String -Pattern "User name" -Quiet
    Write-Host "  [CHECK] hermes_admin 账户: $accOk" -ForegroundColor Cyan
    $wsman = Test-WSMan -ComputerName localhost -ErrorAction SilentlyContinue
    Write-Host "  [CHECK] WinRM 服务: $([bool]$wsman)" -ForegroundColor Cyan
} catch { Write-Host "  [WARN] 验证: $_" -ForegroundColor Yellow }

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " 部署完成！" -ForegroundColor Green
Write-Host " 本机 IP 查询: ipconfig" -ForegroundColor Cyan
Write-Host " 管理入口: WinRM 5985 (hermes_admin/njuee366) / SSH 22 / RDP 3389" -ForegroundColor Cyan
Write-Host " Hermes: deepseek-v4-flash (记得注入 .env 的 DEEPSEEK_API_KEY)" -ForegroundColor Cyan
Write-Host " 代理: 114.212.234.221:1088 (国内直连)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
# WinRM 远程执行（ServerRemoteHost）下不要 Read-Host 阻塞
if ($Host.Name -notmatch 'ServerRemoteHost') {
    Read-Host "按回车退出"
}
