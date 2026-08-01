# Day8 Health Check - Ports + Processes + Real Connectivity
# Exit codes: 0=healthy, 1=zombie (process+port OK but no traffic), 2=down (process or port missing)
param(
    [switch]$Quick  # Skip connectivity test for instant check
)

$ports = @(1088, 1089)
$portOk = $true
foreach ($p in $ports) {
    $listener = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $addr = ($listener | Select-Object -First 1).LocalAddress
        Write-Host "Port $p : LISTENING on $addr"
    } else {
        Write-Host "Port $p : CLOSED"
        if ($p -eq 1088) { $portOk = $false }
    }
}

$svc = Get-Process Day8Svc -ErrorAction SilentlyContinue
$gui = Get-Process Day8 -ErrorAction SilentlyContinue
$svcStatus = if ($svc) { "PID " + $svc.Id } else { "NOT RUNNING" }
$guiStatus = if ($gui) { "PID " + $gui.Id } else { "NOT RUNNING" }
Write-Host "Day8Svc: $svcStatus"
Write-Host "Day8.exe: $guiStatus"

# Quick mode: skip connectivity test
if ($Quick) {
    if ($svc -and $portOk) { exit 0 } else { exit 2 }
}

# Real connectivity test through proxy
if ($portOk -and $svc) {
    try {
        $result = Invoke-WebRequest -Uri "https://httpbin.org/ip" `
            -Proxy "http://127.0.0.1:1088" `
            -TimeoutSec 10 `
            -UseBasicParsing `
            -ErrorAction Stop
        $ip = ($result.Content | ConvertFrom-Json).origin
        Write-Host "Connectivity: OK (exit IP: $ip)"
        exit 0  # Healthy
    } catch {
        $errMsg = $_.Exception.Message
        if ($errMsg -match "timeout|timed|operation canceled") {
            Write-Host "Connectivity: STALE (tunnel timeout - zombie proxy)"
        } else {
            Write-Host "Connectivity: FAIL ($errMsg)"
        }
        exit 1  # Zombie: process+port OK but no traffic
    }
} else {
    Write-Host "Connectivity: DOWN (proxy not running)"
    exit 2  # Down
}
