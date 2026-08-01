# Day8 VPN Manager
# Usage: powershell -File day8_manager.ps1 [start|stop|restart|status|login]
param(
    [ValidateSet("start","stop","restart","status","login")]
    [string]$Action = "status"
)

$ServiceName = "Day8Svc"
$AppPath = "D:\Program Files (x86)\Day8\Day8.exe"
$AppName = "Day8"

function Get-Status {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    $process = Get-Process -Name $AppName -ErrorAction SilentlyContinue

    Write-Host "=== Day8 VPN Status ==="
    Write-Host ""

    if ($service) {
        Write-Host "Service   (Day8Svc): $($service.Status) | Startup: $($service.StartType)"
    } else {
        Write-Host "Service   (Day8Svc): NOT INSTALLED"
    }

    if ($process) {
        $mem = [math]::Round($process.WorkingSet64/1MB, 1)
        Write-Host "GUI       (Day8.exe): Running | PID: $($process.Id) | Start: $($process.StartTime)"
        Write-Host "Memory: $mem MB"
    } else {
        Write-Host "GUI       (Day8.exe): NOT RUNNING"
    }

    # Check proxy port
    $conn = Get-NetTCPConnection -LocalPort 1088 -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq 'Listen' }
    if ($conn) {
        Write-Host "Proxy Port: 127.0.0.1:1088 [LISTENING]"
    } else {
        Write-Host "Proxy Port: 127.0.0.1:1088 [CLOSED]"
    }

    # Check TUN adapter
    $tun = Get-NetAdapter -Name "Day8" -ErrorAction SilentlyContinue
    if ($tun) {
        Write-Host "TUN Adapter: Day8 ($($tun.Status))"
    } else {
        Write-Host "TUN Adapter: Not found"
    }

    # Check system proxy
    $proxy = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -ErrorAction SilentlyContinue
    if ($proxy.ProxyEnable -eq 1) {
        Write-Host "System Proxy: $($proxy.ProxyServer) [ON]"
    } else {
        Write-Host "System Proxy: [OFF] (TUN mode)"
    }

    # Summary
    if ($service -and $service.Status -eq 'Running' -and $conn) {
        Write-Host ""
        Write-Host ">>> VPN is ACTIVE and CONNECTED <<<"
    } elseif ($service -and $service.Status -eq 'Running') {
        Write-Host ""
        Write-Host ">>> VPN service running, waiting for connection <<<"
    } else {
        Write-Host ""
        Write-Host ">>> VPN is STOPPED <<<"
    }
}

function Start-Day8 {
    Write-Host "Starting Day8 VPN..."

    # 1. Start service
    try {
        $service = Get-Service -Name $ServiceName -ErrorAction Stop
        if ($service.Status -ne 'Running') {
            Start-Service -Name $ServiceName
            Write-Host "[OK] Service started"
            Start-Sleep -Seconds 2
        } else {
            Write-Host "[OK] Service already running"
        }
    } catch {
        Write-Host "[FAIL] Service start failed: $_"
    }

    # 2. Start GUI via explorer.exe (avoids admin elevation, Day8 refuses to run as admin)
    if (-not (Get-Process -Name $AppName -ErrorAction SilentlyContinue)) {
        # Use explorer.exe to launch in user context (non-elevated)
        explorer.exe $AppPath
        Write-Host "[OK] GUI launched (explorer, non-admin)"
        Start-Sleep -Seconds 5
    } else {
        Write-Host "[OK] GUI already running"
    }

    Write-Host ""
    Write-Host "Day8 started. Waiting for auto-connect..."
    Start-Sleep -Seconds 3
    Get-Status
}

function Stop-Day8 {
    Write-Host "Stopping Day8 VPN..."

    # 1. Stop GUI
    $processes = Get-Process -Name $AppName -ErrorAction SilentlyContinue
    if ($processes) {
        Stop-Process -Name $AppName -Force
        Write-Host "[OK] GUI closed"
        Start-Sleep -Seconds 1
    } else {
        Write-Host "[OK] GUI not running"
    }

    # 2. Stop service
    try {
        $service = Get-Service -Name $ServiceName -ErrorAction Stop
        if ($service.Status -eq 'Running') {
            Stop-Service -Name $ServiceName -Force
            Write-Host "[OK] Service stopped"
        } else {
            Write-Host "[OK] Service not running"
        }
    } catch {
        Write-Host "[FAIL] Service stop failed: $_"
    }

    Write-Host ""
    Write-Host "Day8 VPN stopped."
    Get-Status
}

function Restart-Day8 {
    Stop-Day8
    Write-Host "Waiting 3s before restart..."
    Start-Sleep -Seconds 3
    Start-Day8
}

function Show-LoginInfo {
    Write-Host "=== Day8 Login Info ==="
    Write-Host ""

    $settingsPath = "$env:LOCALAPPDATA\Day8\settings.json"
    if (Test-Path $settingsPath) {
        try {
            $settings = Get-Content $settingsPath | ConvertFrom-Json

            Write-Host "Preferences: Configured"
            if ($settings.selected_server_id) {
                $sid = $settings.selected_server_id
                Write-Host "Server ID: $($sid.Substring(0, [Math]::Min(24, $sid.Length)))..."
            }
            Write-Host ""
            Write-Host "Note: Credentials are encrypted in settings.json."
            Write-Host "To re-login, open GUI: D:\Program Files (x86)\Day8\Day8.exe"
        } catch {
            Write-Host "Cannot parse settings.json"
        }
    } else {
        Write-Host "No config found. May not be logged in yet."
    }

    # Show recent connection logs
    $logPath = "$env:LOCALAPPDATA\Day8\logs"
    if (Test-Path $logPath) {
        $latestLog = Get-ChildItem "$logPath\network.*.log" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($latestLog) {
            Write-Host ""
            Write-Host "--- Recent connection logs ---"
            Select-String -Path $latestLog.FullName -Pattern "connect|disconnect|error|server" -CaseSensitive:$false |
                Select-Object -Last 8 |
                ForEach-Object { Write-Host $_.Line }
        }
    }
}

Switch ($Action) {
    "start"   { Start-Day8 }
    "stop"    { Stop-Day8 }
    "restart" { Restart-Day8 }
    "status"  { Get-Status }
    "login"   { Show-LoginInfo }
}
