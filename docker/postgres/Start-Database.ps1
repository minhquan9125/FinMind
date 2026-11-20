param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe' }
if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Docker CLI not found. Install/start Docker Desktop and reopen the terminal.' }
$localEnv = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $localEnv)) {
    $bytes = New-Object byte[] 24
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    $localPassword = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    $config = "POSTGRES_DB=finmind`nPOSTGRES_USER=finmind`nPOSTGRES_PASSWORD=$localPassword`nPOSTGRES_PORT=5433`n"
    [System.IO.File]::WriteAllText($localEnv,$config,(New-Object System.Text.UTF8Encoding($false)))
}
Push-Location $projectRoot
try {
    $composeArgs = @('compose','--env-file','docker/postgres/.env','-f','docker-compose.postgres.yml')
    if (Select-String -LiteralPath $localEnv -Pattern '^POSTGRES_LAN_IP=\S+' -Quiet) {
        $composeArgs += @('-f','docker-compose.lan.yml')
    }
    if (-not $VerifyOnly) {
        & $dockerExe @composeArgs up -d --wait --wait-timeout 120
        if ($LASTEXITCODE -ne 0) { throw 'Docker database did not become healthy; inspect compose logs.' }
    }
    & $dockerExe @composeArgs exec -T postgres psql -U finmind -d finmind -v ON_ERROR_STOP=1 -f /opt/finmind-verify-empty.sql
    if ($LASTEXITCODE -ne 0) { throw 'Empty-schema verification failed (or data has already been loaded).' }
} finally { Pop-Location }
