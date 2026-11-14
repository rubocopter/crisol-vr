#Requires -Version 5.1
<#
.SYNOPSIS
Reviewable, opt-in SMB setup on CORSARIO. Run -DryRun or -WhatIf first.
.DESCRIPTION
No elevation prompt, service starts, guest access, SMB policy changes or broad
firewall group activation. Only the dedicated Builds root is eligible.
New-SmbShare's native WhatIf is unreliable: our own early return guards it.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [string]$SharePath = 'E:\Builds',
    [ValidateSet('Read', 'Change')][string]$ShareAccess = 'Read',
    [switch]$DryRun
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$shareName = 'ModBuilds'
$ruleName = 'ModBuilds-SMB-CORSARIO-FRACTAL'
$account = 'CORSARIO\Oni'
$localAddress = '192.168.1.4'
$remoteAddress = '192.168.1.154'

function Assert-BuildTree([string]$Root) {
    # Walk explicitly without following reparse points; bound preflight work.
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return }
    $queue = New-Object 'Collections.Generic.Queue[string]'
    $queue.Enqueue($Root)
    $count = 0
    while ($queue.Count) {
        foreach ($entry in Get-ChildItem -LiteralPath $queue.Dequeue() -Force) {
            $count++
            if ($count -gt 10000) { throw 'Builds tree exceeds the 10000-entry preflight limit.' }
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $entry.Name -match '^\.git$|^(saves|games)$') {
                throw "Unsafe descendant in Builds: $($entry.FullName)"
            }
            if ($entry.PSIsContainer) { $queue.Enqueue($entry.FullName) }
        }
    }
}

if ($env:COMPUTERNAME -ne 'CORSARIO') { throw 'Run this setup only on CORSARIO.' }
if ($SharePath -notmatch '^[Ee]:[\\/]') { throw 'An absolute local E: path is required.' }
if ($SharePath -match '(^|[\\/])\.\.?(?:[\\/]|$)') { throw 'Path traversal is forbidden.' }
$shareRoot = [IO.Path]::GetFullPath($SharePath).TrimEnd('\')
if ($shareRoot -notin @('E:\Builds', 'E:\Proyectos\Builds')) {
    throw 'Only E:\Builds (or the documented E:\Proyectos\Builds fallback) is eligible.'
}
$cursor = $shareRoot
while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
        $item = Get-Item -LiteralPath $cursor -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Not a plain directory: $cursor"
        }
    }
    $parent = Split-Path -Path $cursor -Parent
    if ($parent -eq $cursor) { break }
    $cursor = $parent
}
if (Test-Path -LiteralPath $shareRoot) {
    foreach ($child in Get-ChildItem -LiteralPath $shareRoot -Force) {
        if (-not $child.PSIsContainer -or $child.Name -match '^\.|^(saves|games)$' -or
            ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Unexpected item in dedicated Builds root: $($child.Name)"
        }
    }
}
Assert-BuildTree $shareRoot

Write-Output "Plan: \\CORSARIO\$shareName -> $shareRoot; SMB $ShareAccess only for $account."
Write-Output "NTFS root: $account Modify, SYSTEM/Administrators FullControl; protected inheritance."
Write-Output "Firewall: inbound TCP 445, System/LanmanServer, Private Ethernet, $remoteAddress -> $localAddress."
Write-Output 'Conflicts with ModBuilds or its managed firewall rule cause refusal, never replacement.'
Write-Output 'Other existing firewall rules are left untouched and do not block this setup.'
# Explicit early return: even New-SmbShare is never invoked during previews.
if ($DryRun -or $WhatIfPreference) {
    Write-Output 'PREVIEW ONLY: no changes; live share/ACL/firewall conflict checks require the administrator run.'
    return
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open PowerShell as administrator yourself and rerun. This script never requests elevation.'
}
$accountSid = (New-Object Security.Principal.NTAccount($account)).Translate([Security.Principal.SecurityIdentifier])
$network = Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq $localAddress
if (@($network).Count -ne 1) { throw 'Expected CORSARIO LAN address not found uniquely; review script addresses.' }
$connection = Get-NetConnectionProfile -InterfaceIndex $network.InterfaceIndex
if ($connection.NetworkCategory -ne 'Private') { throw 'LAN must already be Private; no network category is changed.' }
if ($network.InterfaceAlias -ne 'Ethernet') { throw 'Expected Private Ethernet interface; review before adapting.' }
if ((Get-Service -Name LanmanServer).Status -ne 'Running') { throw 'LanmanServer is not running; no service is started.' }

$existingShare = $null
foreach ($share in Get-SmbShare) {
    if ($share.Name -eq $shareName) {
        if ([IO.Path]::GetFullPath($share.Path).TrimEnd('\') -ne $shareRoot) { throw 'ModBuilds points elsewhere.' }
        $existingShare = $share
    } elseif (-not $share.Special -and $share.Path) {
        $other = [IO.Path]::GetFullPath($share.Path).TrimEnd('\')
        if ($other -eq $shareRoot -or $shareRoot.StartsWith($other + '\', [StringComparison]::OrdinalIgnoreCase) -or
            $other.StartsWith($shareRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Overlapping non-administrative share: $($share.Name). Review it manually."
        }
    }
}
if ($existingShare) {
    $access = @(Get-SmbShareAccess -Name $shareName)
    if ($access.Count -ne 1 -or $access[0].AccessControlType -ne 'Allow' -or
        $access[0].AccessRight -ne $ShareAccess -or
        (New-Object Security.Principal.NTAccount($access[0].AccountName)).Translate([Security.Principal.SecurityIdentifier]).Value -ne $accountSid.Value -or
        -not $existingShare.EncryptData -or $existingShare.CachingMode -ne 'None') {
        throw 'Existing ModBuilds permissions/settings conflict; no permissions will be broadened or revoked.'
    }
}
$existingRule = @(Get-NetFirewallRule -PolicyStore PersistentStore -Name $ruleName -ErrorAction SilentlyContinue)
if ($existingRule.Count -gt 1) { throw 'Duplicate managed firewall rule.' }
if ($existingRule.Count -eq 1) {
    $rule = $existingRule[0]
    $port = $rule | Get-NetFirewallPortFilter
    $address = $rule | Get-NetFirewallAddressFilter
    $service = $rule | Get-NetFirewallServiceFilter
    $application = $rule | Get-NetFirewallApplicationFilter
    $interface = $rule | Get-NetFirewallInterfaceFilter
    if ($rule.Direction -ne 'Inbound' -or $rule.Action -ne 'Allow' -or $rule.Enabled -ne 'True' -or
        $rule.Profile.ToString() -ne 'Private' -or $rule.EdgeTraversalPolicy -ne 'Block' -or
        $port.Protocol -notin @('TCP', '6') -or ($port.LocalPort -join ',') -ne '445' -or
        ($address.RemoteAddress -join ',') -ne $remoteAddress -or ($address.LocalAddress -join ',') -ne $localAddress -or
        $service.Service -ne 'LanmanServer' -or $application.Program -ne 'System' -or
        ($interface.InterfaceAlias -join ',') -ne 'Ethernet') {
        throw 'Existing managed firewall rule conflicts; refusing to rewrite it.'
    }
}
# Preflight is complete. This is the only mutation block; no global settings.
if ($PSCmdlet.ShouldProcess($shareRoot, 'Apply bounded ModBuilds share, root ACL and Private firewall rule')) {
    if (-not (Test-Path -LiteralPath $shareRoot)) { New-Item -ItemType Directory -Path $shareRoot | Out-Null }
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $propagate = [Security.AccessControl.PropagationFlags]::None
    foreach ($sid in @('S-1-5-18', 'S-1-5-32-544')) {
        $id = New-Object Security.Principal.SecurityIdentifier($sid)
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($id, 'FullControl', $inherit, $propagate, 'Allow')))
    }
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($accountSid, 'Modify', $inherit, $propagate, 'Allow')))
    Set-Acl -LiteralPath $shareRoot -AclObject $acl
    if (-not $existingShare) {
        $options = @{Name = $shareName; Path = $shareRoot; EncryptData = $true; CachingMode = 'None'; FolderEnumerationMode = 'AccessBased'}
        if ($ShareAccess -eq 'Read') { $options.ReadAccess = @($account) } else { $options.ChangeAccess = @($account) }
        New-SmbShare @options | Out-Null
    }
    if ($existingRule.Count -eq 0) {
        New-NetFirewallRule -Name $ruleName -DisplayName 'ModBuilds: CORSARIO to FRACTAL only' `
            -Direction Inbound -Action Allow -Enabled True -Profile Private -Protocol TCP -LocalPort 445 `
            -LocalAddress $localAddress -RemoteAddress $remoteAddress -Program System -Service LanmanServer `
            -InterfaceAlias Ethernet -EdgeTraversalPolicy Block | Out-Null
    }
    Write-Output "Configured \\CORSARIO\$shareName. Authenticate from FRACTAL as $account using its password."
}
