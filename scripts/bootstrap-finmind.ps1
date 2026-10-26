param([switch]$Check, [string]$Root = (Split-Path $PSScriptRoot -Parent))

function Invoke-FinMindProbe {
    param([string]$File, [string[]]$Arguments)
    try {
        $output = @(& $File @Arguments 2>$null)
        return [pscustomobject]@{ Code = $LASTEXITCODE; Text = ($output -join "`n") }
    } catch { return [pscustomobject]@{ Code = 1; Text = '' } }
}

function Find-FinMindPython {
    $candidates = @()
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $candidates += [pscustomobject]@{Exe=$py.Source; Args=@('-3.12')}
        $candidates += [pscustomobject]@{Exe=$py.Source; Args=@('-3.13')}
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { $candidates += [pscustomobject]@{Exe=$python.Source; Args=@()} }
    foreach ($version in @('312','313')) {
        if ($env:LOCALAPPDATA) {
            $path = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"
            if (Test-Path -LiteralPath $path -PathType Leaf) { $candidates += [pscustomobject]@{Exe=$path; Args=@()} }
        }
    }
    foreach ($candidate in $candidates) {
        $probe = Invoke-FinMindProbe $candidate.Exe (@($candidate.Args) + @('-B','-c','import sys; print(str(sys.version_info.major)+chr(46)+str(sys.version_info.minor))'))
        if ($probe.Code -eq 0 -and $probe.Text.Trim() -in @('3.12','3.13')) { return $candidate }
    }
    return $null
}

function Get-FinMindState {
    param([string]$Root)
    $missing = [System.Collections.Generic.List[string]]::new()
    $blockers = [System.Collections.Generic.List[string]]::new()
    foreach ($relative in @('backend\package.json','backend\requirements.txt','frontend\package.json','frontend\package-lock.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $relative) -PathType Leaf)) { $blockers.Add("Thieu file du an: $relative") }
    }
    foreach ($port in @(8000,5173)) {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
        try { $listener.Start() } catch { $blockers.Add("Cong $port dang ban hoac khong kha dung; hay tu dung ung dung dang dung cong.") }
        finally { $listener.Stop() }
    }
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    $needNode = -not ($node -and $npm)
    if ($node) {
        $version = Invoke-FinMindProbe $node.Source @('--version')
        if ($version.Code -ne 0 -or $version.Text -notmatch '^v?(\d+)\.') { $needNode = $true }
        elseif ([int]$Matches[1] -lt 20) { $needNode = $true }
    }
    if ($needNode) { $missing.Add('Node.js LTS >=20 va npm') }
    $venv = Join-Path $Root '.venv'
    $python = Join-Path $venv 'Scripts\python.exe'
    $needVenv = -not (Test-Path -LiteralPath $python -PathType Leaf)
    if ($needVenv -and (Test-Path -LiteralPath $venv)) { $blockers.Add('.venv da ton tai nhung khong chay duoc. Khong tu ghi de; hay sua moi truong thu cong.') }
    if ($needVenv) {
        $missing.Add('Moi truong Python .venv tai goc FinMind')
        if (-not (Find-FinMindPython)) { $missing.Add('Python 3.12 (cai bang winget)') }
    } else {
        $version = Invoke-FinMindProbe $python @('-B','-c','import sys; print(str(sys.version_info.major)+chr(46)+str(sys.version_info.minor))')
        if ($version.Code -ne 0 -or $version.Text.Trim() -notin @('3.12','3.13')) { $blockers.Add('.venv can Python 3.12/3.13 va phai chay duoc. Khong tu xoa hay thay the moi truong cu.') }
    }
    $needBackend = $needVenv
    if (-not $needVenv) {
        $metadataCheck = @'
import importlib.metadata as metadata
import sys
from pip._vendor.packaging.requirements import Requirement
for line in open(sys.argv[1], encoding='utf-8-sig'):
    line = line.strip()
    if not line or line.startswith('#'): continue
    req = Requirement(line)
    if req.marker and not req.marker.evaluate(): continue
    version = metadata.version(req.name)
    if not req.specifier.contains(version, prereleases=True): raise SystemExit(1)
'@
        $probe = Invoke-FinMindProbe $python @('-B','-c',$metadataCheck,(Join-Path $Root 'backend\requirements.txt'))
        $needBackend = $probe.Code -ne 0
        if (-not $needBackend) { $needBackend = (Invoke-FinMindProbe $python @('-B','-m','pip','check')).Code -ne 0 }
    }
    if ($needBackend) { $missing.Add('pip va thu vien backend theo requirements.txt (Torch co the tai nhieu GB)') }
    $needFrontend = $needNode
    if (-not $needNode) {
        $probe = Invoke-FinMindProbe $npm.Source @('--prefix',(Join-Path $Root 'frontend'),'ls','--depth=0','--offline','--loglevel=silent')
        $needFrontend = $probe.Code -ne 0
    }
    if ($needFrontend) { $missing.Add('Thu vien frontend theo package-lock.json (npm ci)') }
    $hasConfig = (Test-Path -LiteralPath (Join-Path $Root '.env') -PathType Leaf) -or (Test-Path -LiteralPath (Join-Path $Root 'backend\.env') -PathType Leaf) -or ($env:DATABASE_URL -and $env:JWT_SECRET_KEY)
    if (-not $hasConfig) { $blockers.Add('Can .env hoac DATABASE_URL va JWT_SECRET_KEY. Nhan cau hinh cua nhom; launcher khong tao gia tri gia.') }
    return [pscustomobject]@{Ready=($missing.Count -eq 0 -and $blockers.Count -eq 0); Missing=$missing.ToArray(); Blockers=$blockers.ToArray(); NeedNode=$needNode; NeedVenv=$needVenv; NeedBackend=$needBackend; NeedFrontend=$needFrontend}
}

function Request-InstallConsent {
    param([string[]]$Items)
    Write-Host 'Can cai/thiet lap:'
    foreach ($item in $Items) { Write-Host "  - $item" }
    Write-Host 'Se tai tu mang (Torch co the nhieu GB), tao .venv cuc bo, cai thu vien va chap nhan dieu khoan goi/nguon winget neu can.'
    $answer = Read-Host 'Ban dong y tai/cai? [y/co = dong y, Enter/n = huy]'
    return ($null -ne $answer -and $answer.Trim().ToLowerInvariant() -in @('y','yes','c','co',([string][char]99 + [char]243)))
}

function Update-FinMindPath {
    $env:Path = $env:Path + ';' + [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}

function Install-FinMindPackage {
    param([string]$Id)
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { Write-Host 'Thieu winget: cai App Installer tu Microsoft Store, hoac Python tu python.org / Node tu nodejs.org, roi chay lai.'; return $false }
    & $winget.Source install --id $Id --exact --source winget --accept-package-agreements --accept-source-agreements | Out-Host
    if ($LASTEXITCODE -eq 3010) { Write-Host 'Can khoi dong lai Windows sau cai dat. Hay khoi dong lai va mo launcher.'; return $false }
    if ($LASTEXITCODE -ne 0) { Write-Host "Cai $Id that bai (ma $LASTEXITCODE)."; return $false }
    Update-FinMindPath
    return $true
}

function Install-FinMindRequirements {
    param([string]$Root, [psobject]$State)
    if ($State.NeedNode -and -not (Install-FinMindPackage 'OpenJS.NodeJS.LTS')) { return $false }
    $python = Join-Path $Root '.venv\Scripts\python.exe'
    if ($State.NeedVenv) {
        $runtime = Find-FinMindPython
        if (-not $runtime) {
            if (-not (Install-FinMindPackage 'Python.Python.3.12')) { return $false }
            $runtime = Find-FinMindPython
        }
        if (-not $runtime -or (Test-Path -LiteralPath (Join-Path $Root '.venv'))) { Write-Host 'Khong tim thay Python phu hop hoac .venv da ton tai; dung de tranh ghi de.'; return $false }
        $arguments = @($runtime.Args) + @('-B','-m','venv',(Join-Path $Root '.venv'))
        & $runtime.Exe @arguments | Out-Host
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python -PathType Leaf)) { return $false }
    }
    if ($State.NeedBackend) {
        & $python -B -m ensurepip --upgrade | Out-Host
        if ($LASTEXITCODE -ne 0) { return $false }
        & $python -B -m pip install -r (Join-Path $Root 'backend\requirements.txt') | Out-Host
        if ($LASTEXITCODE -ne 0) { return $false }
    }
    if ($State.NeedFrontend) {
        $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $npm) { return $false }
        & $npm.Source --prefix (Join-Path $Root 'frontend') ci | Out-Host
        if ($LASTEXITCODE -ne 0) { return $false }
    }
    return $true
}

function Start-FinMind {
    param([string]$Root)
    Start-Process -FilePath $env:ComSpec -WorkingDirectory (Join-Path $Root 'backend') -ArgumentList '/k npm.cmd run dev' -WindowStyle Normal -ErrorAction Stop
    Start-Process -FilePath $env:ComSpec -WorkingDirectory (Join-Path $Root 'frontend') -ArgumentList '/k npm.cmd run dev -- --host localhost --port 5173 --strictPort' -WindowStyle Normal -ErrorAction Stop
    Write-Host 'Da mo hai terminal. Doi backend san sang, roi mo http://localhost:5173/research. Ctrl+C trong tung terminal de dung.'
}

function Invoke-FinMind {
    param([string]$Root, [switch]$Check)
    try {
        $state = Get-FinMindState $Root
        foreach ($item in @($state.Missing)) { Write-Host "[THIEU] $item" }
        foreach ($item in @($state.Blockers)) { Write-Host "[LOI] $item" }
        if (@($state.Blockers).Count -gt 0) { return 1 }
        if (@($state.Missing).Count -gt 0) {
            if ($Check) { return 1 }
            if (-not (Request-InstallConsent $state.Missing)) { Write-Host 'Da huy; khong cai dat hay khoi dong.'; return 1 }
            if (-not (Install-FinMindRequirements $Root $state)) { Write-Host 'Cai dat khong hoan tat. Chua khoi dong ung dung.'; return 1 }
            $state = Get-FinMindState $Root
            if (-not $state.Ready) {
                foreach ($item in @($state.Missing) + @($state.Blockers)) { Write-Host "[CHUA SAN SANG] $item" }
                return 1
            }
        }
        if (-not $state.Ready) { return 1 }
        if ($Check) { Write-Host '[OK] Moi truong cuc bo san sang; ket noi DB/OAuth se duoc ung dung xac nhan khi chay.'; return 0 }
        $null = Start-FinMind $Root
        return 0
    } catch { Write-Host '[LOI] Khong hoan tat kiem tra/cai/khoi dong. Kiem tra duong dan, quyen truy cap va cai dat thu cong neu can.'; return 1 }
}

if ($MyInvocation.InvocationName -ne '.') { exit (Invoke-FinMind -Root $Root -Check:$Check) }
