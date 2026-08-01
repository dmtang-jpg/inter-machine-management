# Office Win11 被管理配置脚本
# 在 Office 上以管理员 PowerShell 运行此脚本

Write-Host "=== 配置 WinRM ==="
Enable-PSRemoting -Force -SkipNetworkProfileCheck
Set-Item -Path WSMan:\localhost\Service\AllowUnencrypted -Value $true -Force
Set-Item -Path WSMan:\localhost\Service\Auth\Basic -Value $true -Force
Restart-Service WinRM
Write-Host "WinRM 完成"

Write-Host "=== 配置 SSH ==="
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 -ErrorAction SilentlyContinue
$cfg = Get-Content "C:\ProgramData\ssh\sshd_config" -ErrorAction SilentlyContinue
if ($cfg) {
    $cfg = $cfg -replace '#UseDNS yes','UseDNS no' -replace 'UseDNS yes','UseDNS no'
    $cfg | Set-Content "C:\ProgramData\ssh\sshd_config"
}
Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
Restart-Service sshd -ErrorAction SilentlyContinue
Write-Host "SSH 完成"

Write-Host "=== 防火墙 ==="
New-NetFirewallRule -DisplayName "SSH-22" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "WinRM-5985" -Direction Inbound -Protocol TCP -LocalPort 5985 -Action Allow -Profile Any -ErrorAction SilentlyContinue

Write-Host "=== 添加煤球 SSH 公钥 ==="
$key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBM5Trh0pnzKxrdiz4cC2saoQmK/QKIZjAv+o+J6Bvxn dm@DESKTOP-97FQ8Q3"
$adminKeyFile = "C:\ProgramData\ssh\administrators_authorized_keys"
Add-Content -Path $adminKeyFile -Value $key -ErrorAction SilentlyContinue
icacls $adminKeyFile /inheritance:r /grant "SYSTEM:F" /grant "Administrators:F" 2>$null

Write-Host "=== 全部完成 ==="
Write-Host "现在可以从煤球管理这台机器了："
Write-Host "  powershell -Exec Bypass -File ~/manage.ps1 office hostname"
