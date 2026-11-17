# Windows x64 restore entry point. Does not copy credentials or alter global PATH.
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $HOME 'TalkingHeadStudio'),
    [string]$ArchivesDirectory,
    [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repository = [IO.Path]::GetFullPath($PSScriptRoot)
$GitHubRepository = '124-creator/talking-head-production-backup-20261117'
$ReleaseTag = 'snapshot-20261117-current'
$InstallerName = 'python-3.13.5-amd64.exe'
$InstallerSha256 = 'c1cb40978b28f696b111c36034a1bdeda17d25e35c74a08ef5e5ff405a63fc20'
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$SavedOutputEncoding = $OutputEncoding
$SavedConsoleEncoding = [Console]::OutputEncoding
$EnvironmentNames = @('PYTHONHOME', 'PYTHONPATH', 'PYTHONNOUSERSITE', 'PYTHONIOENCODING',
    'PIP_CONFIG_FILE', 'PIP_NO_INDEX', 'PIP_DISABLE_PIP_VERSION_CHECK',
    'PLAYWRIGHT_BROWSERS_PATH', 'PLAYWRIGHT_SKIP_BROWSER_GC', 'HF_HUB_OFFLINE',
    'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'PATH', 'HTTP_PROXY', 'HTTPS_PROXY')
$SavedEnvironment = @{}
foreach ($Name in $EnvironmentNames) {
    $SavedEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$ArgumentList)
    & $Executable @ArgumentList | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $Executable $($ArgumentList -join ' ')"
    }
}

function ConvertTo-PythonCommand {
    param([string]$Code)
    # Windows PowerShell 5.1 native argument passing can strip nested quotes.
    $Encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
    return "import base64;exec(base64.b64decode('$Encoded'))"
}

function ConvertTo-HttpProxyUri {
    param([string]$Value)
    $Value = $Value.Trim()
    if (-not $Value) { return $null }
    # WinINET's https= key names the destination protocol, not a TLS proxy.
    if ($Value -notmatch '^[a-z][a-z0-9+.-]*://') { $Value = 'http://' + $Value }
    $Uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$Uri) -or
        $Uri.Scheme -notin @('http', 'https') -or -not $Uri.Host -or
        $Uri.AbsolutePath -ne '/' -or $Uri.Query -or $Uri.Fragment) {
        return $null
    }
    return $Uri.AbsoluteUri.TrimEnd('/')
}

function ConvertFrom-WindowsStaticProxy {
    param([string]$Server)
    $Proxies = @{}
    if ($Server -match '(?i)(?:^|;)\s*(?:http|https|socks)\s*=') {
        foreach ($Entry in $Server.Split(';')) {
            if ($Entry -match '(?i)^\s*(http|https)\s*=\s*(.+?)\s*$') {
                $Protocol = $Matches[1].ToLowerInvariant()
                $Proxy = ConvertTo-HttpProxyUri $Matches[2]
                if ($Proxy) { $Proxies[$Protocol] = $Proxy }
            }
        }
    } else {
        $Proxy = ConvertTo-HttpProxyUri $Server
        if ($Proxy) { $Proxies['http'] = $Proxy; $Proxies['https'] = $Proxy }
    }
    return $Proxies
}

function Initialize-WindowsProxyEnvironment {
    # Go/gh does not automatically inherit WinINET's current-user static proxy.
    # Explicit process environment always wins; never change Windows settings.
    if ($env:HTTP_PROXY -or $env:HTTPS_PROXY -or $env:ALL_PROXY) { return }
    $Settings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
    if (-not $Settings -or -not $Settings.PSObject.Properties['ProxyEnable'] -or
        -not $Settings.PSObject.Properties['ProxyServer'] -or $Settings.ProxyEnable -ne 1) {
        return
    }
    $Proxies = ConvertFrom-WindowsStaticProxy ([string]$Settings.ProxyServer)
    if ($Proxies.ContainsKey('http')) { $env:HTTP_PROXY = $Proxies['http'] }
    if ($Proxies.ContainsKey('https')) { $env:HTTPS_PROXY = $Proxies['https'] }
    if ($Proxies.Count) {
        # Proxy addresses can contain credentials, so do not print them.
        Write-Host 'Using the current-user Windows static proxy for this restore session only.'
    }
}

function Find-Gh {
    $Command = Get-Command gh.exe -CommandType Application -ErrorAction SilentlyContinue
    if (-not $Command) { $Command = Get-Command gh -CommandType Application -ErrorAction SilentlyContinue }
    if (-not $Command) {
        throw 'GitHub CLI (gh) is required for private Release downloads. Install it, run gh auth login, then rerun this script. No token is included in the backup.'
    }
    return $Command.Source
}

function Confirm-GitHubAuthentication {
    param([string]$Gh)
    & $Gh auth status --hostname github.com *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'This computer is not authenticated to GitHub. Run gh auth login with an account allowed to read the private repository, then rerun.'
    }
}

function Get-CompatiblePython {
    $Candidates = New-Object 'System.Collections.Generic.List[object]'
    foreach ($Name in @('python.exe', 'python3.exe', 'python', 'python3')) {
        $Command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue
        if ($Command -and $Command.Source -notmatch '\\WindowsApps\\') {
            $Candidates.Add(@{ Exe = $Command.Source; Prefix = @() })
        }
    }
    $Launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($Launcher) { $Candidates.Add(@{ Exe = $Launcher.Source; Prefix = @('-3.13') }) }
    foreach ($Key in @('HKCU:\Software\Python\PythonCore\3.13\InstallPath',
                        'HKLM:\Software\Python\PythonCore\3.13\InstallPath')) {
        if (Test-Path -LiteralPath $Key) {
            $InstallPath = (Get-Item -LiteralPath $Key).GetValue('')
            if ($InstallPath) {
                $Candidates.Add(@{ Exe = (Join-Path $InstallPath 'python.exe'); Prefix = @() })
            }
        }
    }
    foreach ($Relative in @('TalkingHeadRestore\Python3135\python.exe', 'Programs\Python\Python313\python.exe')) {
        $Candidates.Add(@{ Exe = (Join-Path $env:LOCALAPPDATA $Relative); Prefix = @() })
    }
    $Probe = ConvertTo-PythonCommand 'import json,platform,struct,sys; print(json.dumps({"ok":sys.version_info[:2]==(3,13) and struct.calcsize("P")==8 and platform.system()=="Windows","executable":sys.executable,"version":platform.python_version()}))'
    foreach ($Candidate in $Candidates) {
        if (-not (Test-Path -LiteralPath $Candidate.Exe -PathType Leaf)) { continue }
        try {
            $Arguments = @($Candidate.Prefix) + @('-I', '-X', 'utf8', '-c', $Probe)
            $Text = & $Candidate.Exe @Arguments 2>$null
            if ($LASTEXITCODE -ne 0) { continue }
            $Info = ($Text -join "`n") | ConvertFrom-Json
            if ($Info.ok -and (Test-Path -LiteralPath $Info.executable -PathType Leaf)) {
                Write-Host "Using existing Windows x64 Python $($Info.version): $($Info.executable)"
                return [string]$Info.executable
            }
        } catch {
            # A broken registry entry or unconfigured py launcher is not a Python installation.
        }
    }
    return $null
}

function Install-VerifiedPython {
    $Gh = Find-Gh
    Confirm-GitHubAuthentication $Gh
    $Cache = Join-Path $env:LOCALAPPDATA 'TalkingHeadRestore\Downloads'
    $InstallRoot = Join-Path $env:LOCALAPPDATA 'TalkingHeadRestore\Python3135'
    $Installer = Join-Path $Cache $InstallerName
    New-Item -ItemType Directory -Path $Cache -Force | Out-Null
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
        Write-Host 'Downloading the pinned Python 3.13.5 x64 installer from the private Release...'
        Invoke-Checked $Gh @('release', 'download', $ReleaseTag, '--repo', $GitHubRepository,
            '--pattern', $InstallerName, '--dir', $Cache)
    }
    if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InstallerSha256) {
        throw "Python installer SHA256 mismatch. The suspect file was not executed or overwritten: $Installer"
    }
    $Signature = Get-AuthenticodeSignature -LiteralPath $Installer
    if ($Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate -or
        $Signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw 'Python installer must have a valid Python Software Foundation Authenticode signature. It was not executed.'
    }
    if (Test-Path -LiteralPath $InstallRoot) {
        throw "No compatible Python was found, but the dedicated installation directory already exists. It was not overwritten: $InstallRoot"
    }
    Write-Host "Installing the verified interpreter for this user only: $InstallRoot"
    # No administrator request, global PATH, py launcher, file association, or shortcuts.
    $InstallerArguments = '/quiet InstallAllUsers=0 TargetDir="{0}" PrependPath=0 AppendPath=0 Include_launcher=0 InstallLauncherAllUsers=0 AssociateFiles=0 Shortcuts=0 Include_test=0 Include_pip=1' -f $InstallRoot
    $Process = Start-Process -FilePath $Installer -ArgumentList $InstallerArguments -WindowStyle Hidden -Wait -PassThru
    if ($Process.ExitCode -notin @(0, 3010)) {
        throw "Python installer failed with exit code $($Process.ExitCode). No project files have been overwritten."
    }
    $Python = Get-CompatiblePython
    if (-not $Python) { throw 'The Python installer finished but no runnable Python 3.13 x64 interpreter was found.' }
    return $Python
}

function Assert-NoReparsePoints {
    param([string]$Path)
    $Current = [IO.Path]::GetFullPath($Path)
    while ($Current) {
        if (Test-Path -LiteralPath $Current) {
            $Item = Get-Item -LiteralPath $Current -Force
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing to create or reuse an environment through a junction/symlink: $Current"
            }
        }
        $Parent = [IO.Path]::GetDirectoryName($Current)
        if ($Parent -eq $Current) { break }
        $Current = $Parent
    }
}

function Initialize-IsolatedEnvironment {
    param([string]$Python, [string]$Root, [string]$Kind, [string]$SnapshotId)
    $EnvironmentDirectory = Join-Path $Root 'environment'
    $Venv = Join-Path $EnvironmentDirectory ('.venv-' + $Kind)
    $OwnerPath = Join-Path $EnvironmentDirectory ('.venv-' + $Kind + '.restore-owner.json')
    Assert-NoReparsePoints $Venv
    Assert-NoReparsePoints $OwnerPath
    $CreateEnvironment = $false
    if (Test-Path -LiteralPath $Venv) {
        if (-not (Test-Path -LiteralPath $OwnerPath -PathType Leaf)) {
            throw "Existing environment is not owned by this restore workflow; refusing to modify it: $Venv"
        }
        $Owner = Get-Content -LiteralPath $OwnerPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Owner.snapshot_id -ne $SnapshotId -or $Owner.kind -ne $Kind -or
            [IO.Path]::GetFullPath([string]$Owner.destination) -ne $Root) {
            throw "Environment ownership does not match this snapshot/destination: $Venv"
        }
        if ($Owner.status -eq 'creating') {
            # Retry only this workflow's interrupted creation, never an unrelated venv.
            $CreateEnvironment = $true
        } elseif ($Owner.status -ne 'ready') {
            throw "Unknown existing environment ownership state; refusing to modify it: $Venv"
        }
    } else {
        $Owner = [ordered]@{ snapshot_id = $SnapshotId; kind = $Kind; destination = $Root; status = 'creating' }
        [IO.File]::WriteAllText($OwnerPath, ($Owner | ConvertTo-Json), $Utf8NoBom)
        $CreateEnvironment = $true
    }
    if ($CreateEnvironment) {
        Invoke-Checked $Python @('-I', '-X', 'utf8', '-m', 'venv', $Venv)
    }
    $VenvPython = Join-Path $Venv 'Scripts\python.exe'
    $Config = Join-Path $Venv 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf) -or
        -not (Test-Path -LiteralPath $Config -PathType Leaf) -or
        (Get-Content -LiteralPath $Config -Raw) -notmatch '(?im)^include-system-site-packages\s*=\s*false\s*$') {
        throw "Environment is incomplete or not isolated. It was not replaced: $Venv"
    }
    $Probe = ConvertTo-PythonCommand 'import pathlib,sys; expected=pathlib.Path(sys.argv[1]).resolve(); assert sys.prefix!=sys.base_prefix and pathlib.Path(sys.prefix).resolve()==expected, "Moved or invalid venv"'
    Invoke-Checked $VenvPython @('-I', '-X', 'utf8', '-c', $Probe, $Venv)
    $Wheels = Join-Path $Root ('runtimes\wheels\' + $Kind)
    $Requirements = Join-Path $EnvironmentDirectory ('requirements-' + $Kind + '.lock.txt')
    Write-Host "Installing pinned $Kind packages offline into $Venv"
    Invoke-Checked $VenvPython @('-I', '-X', 'utf8', '-m', 'pip', '--isolated', '--disable-pip-version-check',
        'install', '--no-index', '--find-links', $Wheels, '-r', $Requirements)
    Invoke-Checked $VenvPython @('-I', '-X', 'utf8', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'check')
    $Owner.status = 'ready'
    [IO.File]::WriteAllText($OwnerPath, ($Owner | ConvertTo-Json), $Utf8NoBom)
    return $VenvPython
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
        -not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
        throw 'Run this script from Windows x64 PowerShell (64-bit process).'
    }
    $OutputEncoding = $Utf8NoBom
    [Console]::OutputEncoding = $Utf8NoBom
    [Environment]::SetEnvironmentVariable('PYTHONHOME', $null, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $null, 'Process')
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PIP_CONFIG_FILE = 'NUL'
    $env:PIP_NO_INDEX = '1'
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    Initialize-WindowsProxyEnvironment

    $Destination = [IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Destination)).TrimEnd('\')
    if (-not [IO.Path]::GetDirectoryName($Destination) -or $Destination -eq $Repository) {
        throw 'Choose a dedicated restoration directory, not a drive root or the cloned Git repository itself.'
    }
    Assert-NoReparsePoints $Destination
    if (-not (Test-Path -LiteralPath (Join-Path $Repository 'tools\restore_snapshot.py') -PathType Leaf)) {
        throw 'The clone is incomplete: tools/restore_snapshot.py is missing.'
    }
    if (-not $ArchivesDirectory) {
        Confirm-GitHubAuthentication (Find-Gh)
    } else {
        $ArchivesDirectory = [IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ArchivesDirectory))
        if (-not (Test-Path -LiteralPath $ArchivesDirectory -PathType Container)) {
            throw "Local archive directory does not exist: $ArchivesDirectory"
        }
    }
    $Python = Get-CompatiblePython
    if (-not $Python) { $Python = Install-VerifiedPython }

    $RestoreArguments = @('-I', '-X', 'utf8', (Join-Path $Repository 'tools\restore_snapshot.py'),
        '--repository', $Repository, '--destination', $Destination)
    if ($ArchivesDirectory) { $RestoreArguments += @('--archives-dir', $ArchivesDirectory) }
    Invoke-Checked $Python $RestoreArguments
    $StateFile = Join-Path $Destination '.restore-state.json'
    if (-not (Test-Path -LiteralPath $StateFile -PathType Leaf)) { throw 'Restore tool did not create its ownership/verification marker.' }
    $State = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $Manifest = Get-Content -LiteralPath (Join-Path $Repository 'manifests\snapshot.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $ManifestHash = (Get-FileHash -LiteralPath (Join-Path $Repository 'manifests\snapshot.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($State.status -ne 'verified' -or $State.snapshot_id -ne $Manifest.snapshot_id -or
        $State.manifest_sha256 -ne $ManifestHash) {
        throw 'Restoration is not marked fully verified against this exact snapshot. No environments will be modified.'
    }
    Invoke-Checked $Python @('-I', '-X', 'utf8', (Join-Path $Repository 'tools\relocate_workspace.py'), $Destination, '--apply')

    # Keep environment PATH changes local to this invocation. Activation is explicit.
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $Destination 'runtimes\playwright'
    $env:PLAYWRIGHT_SKIP_BROWSER_GC = '1'
    $env:PATH = (Join-Path $Destination 'runtimes\ffmpeg\bin') + ';' + $env:PATH
    $RenderPython = Initialize-IsolatedEnvironment $Python $Destination 'render' $Manifest.snapshot_id
    $AsrPython = Initialize-IsolatedEnvironment $Python $Destination 'asr' $Manifest.snapshot_id

    if ($SkipSmoke) {
        Write-Warning 'Smoke tests were explicitly skipped. Files are verified, but this invocation does NOT prove the restored project is editable/runnable.'
    } else {
        Write-Host 'Checking both finished masters, restored assets, and bundled Chromium composition seeks...'
        $SmokeArguments = @('-I', '-X', 'utf8', (Join-Path $Repository 'tools\smoke_restored.py'), $Destination)
        $SmokeText = & $RenderPython @SmokeArguments
        if ($LASTEXITCODE -ne 0) { $SmokeText | Write-Host; throw 'Restored renderer smoke test failed.' }
        [IO.File]::WriteAllText((Join-Path $Destination 'environment\smoke-render.json'), ($SmokeText -join "`n"), $Utf8NoBom)
        $Smoke = ($SmokeText -join "`n") | ConvertFrom-Json
        if ($Smoke.status -ne 'passed') { throw 'Renderer reported only a partial diagnostic rather than a full smoke pass.' }
        $SmokeText | Write-Host

        Write-Host 'Loading the bundled Whisper small model offline in the separate isolated ASR environment...'
        $AsrProbe = @'
import json, os, pathlib, sys
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
root = pathlib.Path(sys.argv[1]).resolve()
cfg = pathlib.Path(sys.prefix) / 'pyvenv.cfg'
assert sys.prefix != sys.base_prefix and 'include-system-site-packages = false' in cfg.read_text().lower()
from faster_whisper import WhisperModel
model_path = root / 'models/faster-whisper-small/536b0662742c02347bc0e980a01041f333bce120'
assert model_path.is_dir() and model_path.resolve().is_relative_to(root)
model = WhisperModel(str(model_path), device='cpu', compute_type='int8', cpu_threads=2, num_workers=1, local_files_only=True)
print(json.dumps({'status':'passed','offline':True,'model':str(model_path),'device':'cpu','compute_type':'int8','executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'note':'Local model-load check; no source media was transcribed or overwritten.'}))
'@
        $AsrText = & $AsrPython -I -X utf8 -c (ConvertTo-PythonCommand $AsrProbe) $Destination
        if ($LASTEXITCODE -ne 0) { $AsrText | Write-Host; throw 'Offline ASR model-load test failed.' }
        [IO.File]::WriteAllText((Join-Path $Destination 'environment\smoke-asr.json'), ($AsrText -join "`n"), $Utf8NoBom)
        $AsrText | Write-Host
    }
    Write-Host "Restored project root: $Destination"
    Write-Host 'Read RESTORE_CONTEXT.md before continuing. Existing videos and global Codex skills were not overwritten.'
    Write-Host "Activate in a PowerShell session with: . '$Destination\Activate-Project.ps1'"
    Write-Host 'Bundled skill copies are in skills/; do not blindly overwrite a newer global skill installation.'
} finally {
    foreach ($Name in $EnvironmentNames) {
        [Environment]::SetEnvironmentVariable($Name, $SavedEnvironment[$Name], 'Process')
    }
    $OutputEncoding = $SavedOutputEncoding
    [Console]::OutputEncoding = $SavedConsoleEncoding
}
