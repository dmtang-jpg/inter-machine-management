<#
用法: powershell -File ~/manage.ps1 <target> <command>
示例: powershell -File ~/manage.ps1 linux hostname
#>
param($target, $cmd)

$hosts = @{
    "linux"  = @{ type="ssh";  host="114.212.122.10"; user="dmt" }
    "office" = @{ type="winrm"; host="114.212.123.189"; user="hermes_admin"; pass=$env:WINRM_PASS }
    "meiqiu" = @{ type="winrm"; host="114.212.234.221"; user="DM"; pass=$env:WINRM_PASS }
}

$h = $hosts[$target]
if (-not $h) { Write-Output "未知目标: $target"; exit 1 }

if ($h.type -eq "ssh") {
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$($h.user)@$($h.host)" $cmd
} else {
    $pw = ConvertTo-SecureString $h.pass -AsPlainText -Force
    $cred = New-Object System.Management.Automation.PSCredential($h.user, $pw)
    $opt = New-PSSessionOption -SkipCACheck -SkipCNCheck
    $sess = New-PSSession -ComputerName $h.host -Credential $cred -SessionOption $opt -Authentication Basic -Port 5985
    Invoke-Command -Session $sess { param($c) Invoke-Expression $c } -ArgumentList $cmd
    Remove-PSSession $sess
}
