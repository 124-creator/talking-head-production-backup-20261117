# Dot-source this file AFTER a successful restore:
#   . 'D:\TalkingHeadStudio\Activate-Project.ps1'
# Only the current PowerShell process environment is changed.
[CmdletBinding()]
param([ValidateSet('render', 'asr')][string]$Environment = 'render')

$ProjectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$MarkerPath = Join-Path $ProjectRoot '.restore-state.json'
if (-not (Test-Path -LiteralPath $MarkerPath -PathType Leaf)) {
    throw 'Run Restore.ps1 first. Activate the copy at the restored project root, not the Git clone.'
}
$Marker = Get-Content -LiteralPath $MarkerPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Marker.status -ne 'verified') { throw 'The restored project has not passed complete snapshot verification.' }
$Venv = Join-Path $ProjectRoot ('environment\.venv-' + $Environment)
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$VenvConfig = Join-Path $Venv 'pyvenv.cfg'
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf) -or
    -not (Test-Path -LiteralPath $VenvConfig -PathType Leaf) -or
    (Get-Content -LiteralPath $VenvConfig -Raw) -notmatch '(?im)^include-system-site-packages\s*=\s*false\s*$') {
    throw "Missing or non-isolated $Environment environment. Complete Restore.ps1 before activation."
}

# A single pre-activation snapshot supports switching render/asr without stacking PATHs.
if (-not (Get-Variable -Name TalkingHeadEnvironmentBeforeActivation -Scope Global -ErrorAction SilentlyContinue)) {
    $global:TalkingHeadEnvironmentBeforeActivation = @{}
    foreach ($Name in @('PATH', 'VIRTUAL_ENV', 'PYTHONHOME', 'PYTHONPATH', 'PYTHONNOUSERSITE',
        'PYTHONIOENCODING', 'PLAYWRIGHT_BROWSERS_PATH', 'PLAYWRIGHT_SKIP_BROWSER_GC',
        'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'TALKING_HEAD_ROOT')) {
        $global:TalkingHeadEnvironmentBeforeActivation[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
    }
}
$env:PATH = (Join-Path $Venv 'Scripts') + ';' + (Join-Path $ProjectRoot 'runtimes\ffmpeg\bin') + ';' +
    $global:TalkingHeadEnvironmentBeforeActivation['PATH']
$env:VIRTUAL_ENV = $Venv
[Environment]::SetEnvironmentVariable('PYTHONHOME', $null, 'Process')
[Environment]::SetEnvironmentVariable('PYTHONPATH', $null, 'Process')
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $ProjectRoot 'runtimes\playwright'
$env:PLAYWRIGHT_SKIP_BROWSER_GC = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:TALKING_HEAD_ROOT = $ProjectRoot

function global:Exit-TalkingHeadEnvironment {
    foreach ($Name in $global:TalkingHeadEnvironmentBeforeActivation.Keys) {
        [Environment]::SetEnvironmentVariable($Name, $global:TalkingHeadEnvironmentBeforeActivation[$Name], 'Process')
    }
    Remove-Variable -Name TalkingHeadEnvironmentBeforeActivation -Scope Global
    Remove-Item -LiteralPath 'Function:\Exit-TalkingHeadEnvironment'
}
Write-Host "Active talking-head $Environment environment: $Venv"
Write-Host 'Original source audio and existing masters remain unchanged. Run Exit-TalkingHeadEnvironment to restore this session environment.'
