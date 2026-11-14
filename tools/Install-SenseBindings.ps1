<#
.SYNOPSIS
Prepare a native Sense SteamVR OpenXR binding. Windows PowerShell 5.1; no Python.
.DESCRIPTION
Default is preview. -Write writes a separate offline file, never a live autosave.
If -Actions is omitted, reads getactions.json from local SteamVR. No network writes.
Use SteamVR Binding UI to activate the reviewed result; see profile/steamvr/README.txt.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Binding,
    [Parameter(Mandatory = $true)][string]$XrLog,
    [Parameter(Mandatory = $true)][string]$Output,
    [string]$Actions,
    [string]$Template,
    [switch]$Write
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

function Require($Condition, [string]$Reason) {
    if (-not $Condition) { throw $Reason }
}
function Has($Object, [string]$Name) {
    return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name]
}
function Load-Json([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}
function Check-OfflinePath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    Require ($full -notmatch '(?i)[\\/]Steam[\\/]config(?:[\\/]|$)|[\\/]steamvr[\\/]input(?:[\\/]|$)') 'Output must be outside Steam/config and steamvr/input'
    $parent = [IO.DirectoryInfo]([IO.Path]::GetDirectoryName($full))
    while ($null -ne $parent) {
        Require (($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'Output parent cannot be a junction or symbolic link'
        Require (-not (Test-Path -LiteralPath (Join-Path $parent.FullName 'steam.exe'))) 'Output cannot be inside a Steam installation'
        Require (-not (Test-Path -LiteralPath (Join-Path $parent.FullName 'vrserver.exe'))) 'Output cannot be inside SteamVR'
        $parent = $parent.Parent
    }
    if (Test-Path -LiteralPath $full) {
        Require (((Get-Item -LiteralPath $full).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'Output cannot be a symbolic link'
    }
    return $full
}

try {
    $appKey = 'steam.app.1790930'
    $controller = 'playstation_vr2_sense'
    $actionSet = '/actions/defaultopenxr'
    $interaction = '/interaction_profiles/valve/index_controller'
    $outputPath = Check-OfflinePath $Output
    if (-not $Template) {
        foreach ($candidate in @((Join-Path $PSScriptRoot '../profile/steamvr/crisol_sense_openxr.json'),
                                  (Join-Path $PSScriptRoot 'steamvr/crisol_sense_openxr.json'),
                                  (Join-Path $PSScriptRoot 'crisol_sense_openxr.json'))) {
            if (Test-Path -LiteralPath $candidate) { $Template = $candidate; break }
        }
    }
    Require ([bool]$Template) 'Native template not found; pass -Template with the kit JSON'
    foreach ($evidence in @($Binding, $XrLog, $Template, $Actions)) {
        if ($evidence) { Require ($outputPath -ne [IO.Path]::GetFullPath($evidence)) 'Output must differ from evidence/template' }
    }
    $logText = Get-Content -LiteralPath $XrLog -Raw -Encoding UTF8
    $starts = [regex]::Matches($logText, 'CRToiPrototype-Win64-Shipping[^\r\n]*startup with PID=')
    Require ($starts.Count -gt 0) 'Expected Crisol xrclient log with startup marker'
    $session = $logText.Substring($starts[$starts.Count - 1].Index)
    Require ($session.Contains('vrclient type=VRApplication_OpenXRInstance')) 'Latest Crisol run must be OpenXR'
    $keys = [regex]::Matches($session, 'xrCreateSession: Creating session for ([^\s]+)')
    Require ($keys.Count -gt 0) 'No OpenXR session app key in latest Crisol run'
    Require ($keys[$keys.Count - 1].Groups[1].Value -eq $appKey) 'Wrong application in latest Crisol session'

    $nativeExport = Load-Json $Binding
    if (Has $nativeExport 'binding_config') {
        Require ($nativeExport.success -eq $true -and $nativeExport.app_key -eq $appKey) 'Unsuccessful/wrong-app binding response'
        $nativeExport = $nativeExport.binding_config
        if (-not (Has $nativeExport 'app_key')) { $nativeExport | Add-Member app_key $appKey }
    }
    Require ($nativeExport.app_key -eq $appKey) 'Wrong/missing app_key in exported binding'
    Require ($nativeExport.category -eq 'openxr') 'Export must be OpenXR'
    Require ($nativeExport.controller_type -eq $controller) 'Export must be native playstation_vr2_sense; export from Binding UI, do not rename compatibility JSON'
    $exportSets = @($nativeExport.bindings.PSObject.Properties.Name)
    Require ($exportSets.Count -eq 1 -and $exportSets[0] -eq $actionSet) 'Unexpected/missing UEVR action sets'
    if (Has $nativeExport 'simulated_actions') { Require (@($nativeExport.simulated_actions).Count -eq 0) 'Simulated actions require manual review' }

    if ($Actions) { $registry = Load-Json $Actions }
    else {
        # Same read-only endpoint used by the installed Valve Binding UI.
        $registry = Invoke-RestMethod -Uri ('http://127.0.0.1:27062/input/getactions.json?app_key=' + $appKey) -TimeoutSec 5
    }
    Require ($registry.category -eq 'openxr') 'Action registry must be OpenXR'
    if (Has $registry 'app_key') { Require ($registry.app_key -eq $appKey) 'Wrong application in action registry' }
    Require ((Has $registry.current_binding_url $controller) -and [bool]$registry.current_binding_url.$controller) 'Registry has no native Sense binding URL'
    Require ($registry.interaction_profiles -contains $interaction) 'Running app must accept Valve Index interaction profile'
    $registered = @{}
    foreach ($set in $registry.action_sets) {
        foreach ($action in $set.actions) {
            Require (-not $registered.ContainsKey($action.name)) 'Duplicate registered action'
            Require ($action.name.StartsWith($set.name + '/', [StringComparison]::Ordinal)) 'Action outside its registered set'
            $registered[$action.name] = $action.type
        }
    }
    $result = Load-Json $Template
    Require ($result.app_key -eq $appKey -and $result.category -eq 'openxr' -and $result.controller_type -eq $controller) 'Wrong native template app/API/controller'
    Require ($result.interaction_profile -eq $interaction) 'Wrong template interaction profile'
    Require (@($result.options.PSObject.Properties).Count -eq 0) 'Template must not simulate controllers/HMD'
    $templateSets = @($result.bindings.PSObject.Properties.Name)
    Require ($templateSets.Count -eq 1 -and $templateSets[0] -eq $actionSet) 'Wrong template action set'
    $section = $result.bindings.$actionSet
    Require ($section.sources.Count -eq 20 -and $section.poses.Count -eq 4 -and $section.haptics.Count -eq 2) 'Incomplete native template'
    $create = @($section.sources | Where-Object path -eq '/user/hand/left/input/create')
    Require ($create.Count -eq 1 -and $create[0].mode -eq 'button' -and $create[0].inputs.click.output -eq ($actionSet + '/in/abuttontouchright')) 'Create must use its reserved left-hand View marker'
    # Save Personal omits the empty eyetracking array in the verified native file.
    Require (@($section.chords).Count -eq 0 -and (-not (Has $section 'eyetracking') -or @($section.eyetracking).Count -eq 0)) 'Unexpected chord/eye bindings'
    $types = @{trigger='boolean'; grip='boolean'; joystickclick='boolean'; systembutton='boolean';
        abuttonright='boolean'; abuttonleft='boolean'; bbuttonright='boolean'; bbuttonleft='boolean';
        abuttontouchright='boolean'; abuttontouchleft='boolean'; bbuttontouchright='boolean'; bbuttontouchleft='boolean';
        thumbresttouchleft='boolean'; thumbresttouchright='boolean'; joystick='vector2'; pose='pose'; grippose='pose'; haptic='vibration'}
    $seen = @{}
    foreach ($entry in @($section.sources) + @($section.poses) + @($section.haptics)) {
        if (Has $entry 'inputs') {
            $outputs = @($entry.inputs.PSObject.Properties.Value | ForEach-Object { $_.output })
            foreach ($channel in $entry.inputs.PSObject.Properties.Name) {
                Require ($channel -in @('click', 'touch', 'position')) 'Only direct click/touch/position is supported'
                Require ($entry.mode -eq $(if ($channel -eq 'position') {'joystick'} else {'button'})) 'Wrong source mode; Options must not be complex_button/single'
            }
            Require ($entry.path -match '^/user/hand/(left|right)/input/(l1|r1|l2|r2|left_stick|right_stick|cross|circle|square|triangle|options|create)$') 'Unexpected Sony input'
            if ($entry.path -match '/[lr][12]$' -and (Has $entry 'parameters')) {
                Require (-not (Has $entry.parameters 'force_input')) 'Sony L1/R1/L2/R2 expose value, not hardware click'
            }
        } else { $outputs = @($entry.output) }
        foreach ($actionPath in $outputs) {
            $name = $actionPath.Substring($actionPath.LastIndexOf('/') + 1)
            Require ($types.ContainsKey($name)) ('Unknown template action: ' + $actionPath)
            $direction = if ($types[$name] -eq 'vibration') {'out'} else {'in'}
            Require ($actionPath -eq ($actionSet + '/' + $direction + '/' + $name)) 'Wrong template action prefix/direction'
            Require ($registered.ContainsKey($actionPath) -and $registered[$actionPath] -eq $types[$name]) ('Missing/incompatible action: ' + $actionPath)
            $seen[$name] = $true
        }
    }
    Require ($seen.Count -eq $types.Count) 'Incomplete native actions'
    if (Has $registry 'version') { $result | Add-Member action_manifest_version $registry.version -Force }
    $payload = ($result | ConvertTo-Json -Depth 100) + "`n"
    if ($Write) {
        Require (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($outputPath)) -PathType Container) 'Output directory must already exist'
        $old = if (Test-Path -LiteralPath $outputPath) { [IO.File]::ReadAllText($outputPath) } else { $null }
        if ($old -ceq $payload) { Write-Output 'Unchanged (idempotent).' }
        else {
            if ($null -ne $old) {
                $backup = $outputPath + '.' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ') + '.bak'
                [IO.File]::Copy($outputPath, $backup, $false)
                Write-Output ('Backup: ' + $backup)
            }
            $pending = $outputPath + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
            try {
                [IO.File]::WriteAllText($pending, $payload, (New-Object Text.UTF8Encoding($false)))
                $current = if (Test-Path -LiteralPath $outputPath) { [IO.File]::ReadAllText($outputPath) } else { $null }
                Require ($current -ceq $old) 'Output changed during preparation; retry'
                Move-Item -LiteralPath $pending -Destination $outputPath -Force
            } finally { if (Test-Path -LiteralPath $pending) { Remove-Item -LiteralPath $pending } }
        }
        Write-Output ('Prepared offline: ' + $outputPath)
    } else { Write-Output ('Preview only; add -Write to prepare: ' + $outputPath) }
    Write-Output 'Validated steam.app.1790930 / playstation_vr2_sense / OpenXR; Options=direct click.'
    Write-Output 'Not activated. Follow the kit instructions to select in SteamVR and test in headset.'
    exit 0
} catch {
    [Console]::Error.WriteLine('Refused: ' + $_.Exception.Message)
    exit 2
}
