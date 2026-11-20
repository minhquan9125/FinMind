param(
    [string]$LocalIP = '192.168.101.46',
    [string]$Subnet = '192.168.101.0/24',
    [string]$InterfaceAlias = 'Ethernet',
    [int]$Port = 5433
)
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script in PowerShell as Administrator to add the scoped firewall rule.'
}
$ruleName = "FinMind-Postgres-LAN-$Port"
$rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound -Action Allow -Profile Any -Protocol TCP -LocalPort $Port -LocalAddress $LocalIP -RemoteAddress $Subnet -InterfaceAlias $InterfaceAlias -EdgeTraversalPolicy Block | Out-Null
} else {
    New-NetFirewallRule -Name $ruleName -DisplayName 'FinMind PostgreSQL - LAN only' -Enabled True -Direction Inbound -Action Allow -Profile Any -Protocol TCP -LocalPort $Port -LocalAddress $LocalIP -RemoteAddress $Subnet -InterfaceAlias $InterfaceAlias -EdgeTraversalPolicy Block | Out-Null
}
Write-Output "Firewall enabled: TCP $Port on $LocalIP, only from $Subnet via $InterfaceAlias."
