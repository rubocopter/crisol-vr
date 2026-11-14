#Requires -Version 5.1
<#
.SYNOPSIS
Create a bounded, timestamped diagnostic/profile backup on FRACTAL (no admin).
.DESCRIPTION
Reads selected UEVR profile files, recent game/UEVR logs, SteamVR server and
this game's XR-client logs, SteamVR settings and binding JSON. Never imports a
profile, stops a game, reads Steam login/config.vdf, or sends to another PC.
An explicit -Destination may be a share; the default is always local.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$GameExe = 'CRToiPrototype-Win64-Shipping',
    [ValidatePattern('^\d{1,12}$')][string]$SteamAppId = '1790930',
    [string]$ProfilePath = (Join-Path $env:APPDATA 'UnrealVRMod\CRToiPrototype-Win64-Shipping'),
    [string]$SteamPath = (Join-Path ${env:ProgramFiles(x86)} 'Steam'),
    [string]$SteamLibrary = '',
    [string]$GameLogPath = (Join-Path $env:LOCALAPPDATA 'CRToiPrototype\Saved\Logs'),
    [string]$UEVRLogPath = '',
    [string]$Destination = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Crisol-Diagnostics'),
    [ValidateRange(1, 200)][int]$MaxFiles = 100,
    [ValidateRange(1, 64)][int]$MaxTotalMiB = 32,
    [ValidateRange(1, 8192)][int]$LogTailKiB = 256
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($GameExe -notmatch '^[A-Za-z0-9_-]{1,96}$') { throw 'GameExe must be a simple executable basename.' }

function Get-PlainPath([string]$Value) {
    if ($Value -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+)' -or $Value -match '(^|[\\/])\.\.?(?:[\\/]|$)') {
        throw "Absolute path without traversal required: $Value"
    }
    $full = [IO.Path]::GetFullPath($Value).TrimEnd('\')
    if ($full -eq [IO.Path]::GetPathRoot($full).TrimEnd('\')) { throw 'A filesystem root is not a source/destination.' }
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Links/junctions are forbidden: $cursor"
            }
        }
        $parent = Split-Path -Path $cursor -Parent
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
    return $full
}
$ProfilePath = Get-PlainPath $ProfilePath
$SteamPath = Get-PlainPath $SteamPath
$GameLogPath = Get-PlainPath $GameLogPath
$Destination = Get-PlainPath $Destination
if (-not $SteamLibrary) { $SteamLibrary = $SteamPath }
$SteamLibrary = Get-PlainPath $SteamLibrary
if ($UEVRLogPath) { $UEVRLogPath = Get-PlainPath $UEVRLogPath }
foreach ($sourceRoot in @($ProfilePath, $SteamPath, $SteamLibrary, $GameLogPath, $UEVRLogPath)) {
    if ($sourceRoot -and ($Destination -eq $sourceRoot -or $Destination.StartsWith($sourceRoot + '\', [StringComparison]::OrdinalIgnoreCase))) {
        throw 'Diagnostic output must be outside source directories.'
    }
}
if (-not $PSCmdlet.ShouldProcess($Destination, 'Create timestamped bounded diagnostic ZIP')) { return }

$candidates = New-Object 'Collections.Generic.List[object]'
$notes = New-Object 'Collections.Generic.List[string]'
$files = New-Object 'Collections.Generic.List[object]'
$seen = @{}
$totalBytes = 0L
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$stage = Join-Path $Destination ('.pending-' + $stamp)
$pendingZip = Join-Path $Destination ('.pending-' + $stamp + '.zip')
$zipPath = Join-Path $Destination ('Crisol-diagnostics-' + $stamp + '.zip')

function Add-Candidate([string]$Path, [string]$ArchivePath, [bool]$Tail = $false) {
    if ($candidates.Count -ge 400) { return }
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        try {
            $plain = Get-PlainPath $Path
            if ([IO.Path]::GetFileName($plain) -match '(?i)credential|password|secret|token|login|cookie|config\.vdf') { return }
            if (-not $seen.ContainsKey($plain)) {
                $seen[$plain] = $true
                $candidates.Add([pscustomobject]@{Path = $plain; ArchivePath = $ArchivePath; Tail = $Tail})
            }
        } catch { $notes.Add("Skipped unsafe source: $ArchivePath") }
    }
}
function Add-Logs([string]$Directory, [string[]]$Patterns, [string]$Prefix) {
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { $notes.Add("Missing source: $Prefix"); return }
    try { $null = Get-PlainPath $Directory } catch { $notes.Add("Skipped unsafe source: $Prefix"); return }
    # Enumerate only one directory, select the three latest for each named log family.
    foreach ($pattern in $Patterns) {
        Get-ChildItem -LiteralPath $Directory -Filter $pattern -File |
            Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 3 | ForEach-Object {
                Add-Candidate $_.FullName ($Prefix + '/' + $_.Name) $true
            }
    }
}

foreach ($name in @('config.txt', 'cameras.txt', 'cvars_data.txt', 'cvars_standard.txt', 'user_script.txt', 'PSVR2_SENSE.txt', 'PRUEBA_OTRO_PC.txt')) {
    Add-Candidate (Join-Path $ProfilePath $name) ('profile/' + $name)
}
if (Test-Path -LiteralPath $ProfilePath -PathType Container) {
    Get-ChildItem -LiteralPath $ProfilePath -Filter '_interaction_profiles_*.json' -File | Select-Object -First 40 | ForEach-Object {
        Add-Candidate $_.FullName ('profile/' + $_.Name)
    }
    foreach ($sub in @('scripts', 'scripts\libs', 'scripts\libs\config', 'scripts\libs\core', 'scripts\libs\enums', 'scripts\libs\deprecated', 'data', 'uobjecthook', 'steamvr')) {
        $dir = Join-Path $ProfilePath $sub
        if (Test-Path -LiteralPath $dir -PathType Container) {
            try { $null = Get-PlainPath $dir } catch { $notes.Add("Skipped unsafe source: profile/$sub"); continue }
            Get-ChildItem -LiteralPath $dir -File | Where-Object {
                ($sub -in @('data', 'uobjecthook', 'steamvr') -and $_.Extension -eq '.json') -or ($sub -like 'scripts*' -and $_.Extension -eq '.lua')
            } | Select-Object -First 60 | ForEach-Object {
                Add-Candidate $_.FullName ('profile/' + $sub.Replace('\', '/') + '/' + $_.Name)
            }
        }
    }
} else { $notes.Add('Missing source: UEVR game profile') }
Add-Logs $ProfilePath @('*.log', 'UEVR*.txt') 'uevr/logs'
if ($UEVRLogPath) { Add-Logs $UEVRLogPath @('*.log', 'UEVR*.txt') 'uevr/extra-logs' }
Add-Logs $GameLogPath @('*.log') 'game/logs'
Add-Logs (Join-Path $SteamPath 'logs') @('vrserver*.txt', "vrclient*$GameExe*.txt", "vrclient*$GameExe*.log", "xrclient*$GameExe*.txt", "xrclient*$GameExe*.log") 'steam/logs'
Add-Candidate (Join-Path $SteamPath 'config\steamvr.vrsettings') 'steam/config/steamvr.vrsettings'
Add-Candidate (Join-Path $SteamLibrary 'steamapps\common\SteamVR\resources\settings\default.vrsettings') 'steamvr/default.vrsettings'
# SteamVR's saved per-application bindings use app-specific vrapp filenames.
foreach ($bindingKind in @('input', 'openxr')) {
    $bindingDir = Join-Path $SteamPath ('config\' + $bindingKind)
    $bindingArchive = if ($bindingKind -eq 'openxr') { 'steam/bindings/openxr/' } else { 'steam/bindings/' }
    if (Test-Path -LiteralPath $bindingDir -PathType Container) {
    try {
        $null = Get-PlainPath $bindingDir
        Get-ChildItem -LiteralPath $bindingDir -File | Where-Object {
            $_.Extension -eq '.json' -and ($_.Name -like "*$GameExe*" -or $_.Name -like "*steam.app.$SteamAppId*")
        } | Select-Object -First 20 | ForEach-Object {
            Add-Candidate $_.FullName ($bindingArchive + $_.Name)
        }
    } catch { $notes.Add('Skipped unsafe source: steam/bindings/' + $bindingKind) }
    }
}

try {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    foreach ($item in $candidates) {
        if ($files.Count -ge $MaxFiles) { $notes.Add('File count limit reached.'); break }
        try {
            $null = Get-PlainPath $item.Path
            $source = Get-Item -LiteralPath $item.Path
            if (-not $item.Tail -and $source.Length -gt 1MB) { $notes.Add("Skipped oversized config: $($item.ArchivePath)"); continue }
            $sourceLength = $source.Length
            $sourceTime = $source.LastWriteTimeUtc.ToString('o')
            $stream = [IO.File]::Open($item.Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            try {
                $offset = 0L
                if ($item.Tail) { $offset = [Math]::Max(0L, $stream.Length - ($LogTailKiB * 1KB)) }
                $null = $stream.Seek($offset, [IO.SeekOrigin]::Begin)
                $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8, $true)
                # Bound the read even if a live writer keeps appending.
                $readLimit = 1MB
                if ($item.Tail) { $readLimit = $LogTailKiB * 1KB }
                $buffer = New-Object char[] ([int][Math]::Min($readLimit, $stream.Length - $offset))
                $count = $reader.ReadBlock($buffer, 0, $buffer.Length)
                $content = -join $buffer[0..([Math]::Max(0, $count - 1))]
                if ($count -eq 0) { $content = '' }
            } finally { $stream.Dispose() }
            # Remove common credential fields if present in otherwise relevant text.
            $redacted = [regex]::Replace($content, '(?im)(["\x27]?(?:password|passwd|access_token|refresh_token|token|secret|api_key|authorization|cookie|sessionid)["\x27]?\s*[:=]\s*)(?:"[^"\r\n]*"|[^\r\n,}]+)', '$1"[REDACTED]"')
            $redacted = [regex]::Replace($redacted, '(?i)Bearer\s+[A-Za-z0-9._~+/-]+=*', 'Bearer [REDACTED]')
            $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($redacted)
            if ($totalBytes + $bytes.Length -gt ($MaxTotalMiB * 1MB)) { $notes.Add("Total size limit: $($item.ArchivePath)"); continue }
            $target = Join-Path $stage $item.ArchivePath.Replace('/', '\')
            $hash = [Security.Cryptography.SHA256]::Create()
            try { $digest = [BitConverter]::ToString($hash.ComputeHash($bytes)).Replace('-', '').ToLowerInvariant() }
            finally { $hash.Dispose() }
            $after = Get-Item -LiteralPath $item.Path
            New-Item -ItemType Directory -Path (Split-Path -Path $target -Parent) -Force | Out-Null
            [IO.File]::WriteAllBytes($target, $bytes)
            $files.Add([pscustomobject]@{
                archive_path = $item.ArchivePath; bytes = $bytes.Length
                sha256 = $digest
                source_bytes = $sourceLength; source_modified_utc = $sourceTime
                tail_only = ($offset -gt 0); redacted = ($redacted -cne $content)
                source_changed_during_read = ($after.Length -ne $sourceLength -or $after.LastWriteTimeUtc.ToString('o') -ne $sourceTime)
            })
            $totalBytes += $bytes.Length
        } catch { $notes.Add("Could not read: $($item.ArchivePath) [$($_.Exception.GetType().Name)]") }
    }
    $manifest = [ordered]@{
        schema_version = 1; captured_utc = [DateTime]::UtcNow.ToString('o'); game_exe = $GameExe
        host_name = $env:COMPUTERNAME; files = @($files.ToArray()); notes = @($notes.ToArray())
        limits = @{max_files = $MaxFiles; max_total_mib = $MaxTotalMiB; log_tail_kib = $LogTailKiB}
        capture = 'Selected text files only; UTF-8 backup with credential-field redaction; logs may be live.'
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $stage 'manifest.json') -Encoding UTF8
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Add-Type -AssemblyName System.IO.Compression
    $archive = [IO.Compression.ZipFile]::Open($pendingZip, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in @($files | ForEach-Object { $_.archive_path }) + @('manifest.json')) {
            $null = [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, (Join-Path $stage $name), $name)
        }
    } finally { $archive.Dispose() }
    $verify = [IO.Compression.ZipFile]::OpenRead($pendingZip)
    try {
        if ($verify.Entries.Count -ne ($files.Count + 1)) {
            throw "Unexpected diagnostic ZIP entries: $($verify.Entries.Count), expected $($files.Count + 1). $($notes -join '; ')"
        }
        foreach ($file in $files) {
            $entry = $verify.GetEntry($file.archive_path)
            if (-not $entry) { throw "Missing diagnostic entry: $($file.archive_path)" }
            $inputStream = $entry.Open()
            $hash = [Security.Cryptography.SHA256]::Create()
            try { $digest = [BitConverter]::ToString($hash.ComputeHash($inputStream)).Replace('-', '').ToLowerInvariant() }
            finally { $inputStream.Dispose(); $hash.Dispose() }
            if ($digest -ne $file.sha256) { throw 'Diagnostic ZIP hash mismatch.' }
        }
    } finally { $verify.Dispose() }
    [IO.File]::Move($pendingZip, $zipPath)
    Write-Output "Diagnostic backup: $zipPath"
    Write-Output "Selected files: $($files.Count); payload bytes: $totalBytes; notes: $($notes.Count)."
} finally {
    # Checked, unique staging paths under the explicit/default destination only.
    if ((Split-Path -Path $stage -Parent) -ne $Destination -or (Split-Path -Path $stage -Leaf) -notlike '.pending-*') {
        throw 'Unsafe staging cleanup target.'
    }
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    if (Test-Path -LiteralPath $pendingZip) { Remove-Item -LiteralPath $pendingZip -Force }
}
