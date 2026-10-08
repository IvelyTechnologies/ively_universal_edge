param(
    [int]$Port = 2025
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$state = Join-Path $root '.local-state'

New-Item -ItemType Directory -Force -Path $state | Out-Null
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $root
$env:IVELY_EDGE_DIR = $root
$env:IVELY_AGENT_DIR = $state
$env:IVELY_MEDIAMTX_DIR = Join-Path $state 'mediamtx'
$env:IVELY_MEDIAMTX_CONFIG = Join-Path $env:IVELY_MEDIAMTX_DIR 'mediamtx.yml'
$env:IVELY_PROVISIONED_MARKER = Join-Path $state '.provisioned'

python -c "import fastapi, onvif, requests, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Missing Python dependencies. Run: python -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "Local unified setup: http://127.0.0.1:$Port/sources"
Write-Host "Temporary test files: $state"
python -m uvicorn main:app --app-dir (Join-Path $root 'provision-ui') --host 127.0.0.1 --port $Port
