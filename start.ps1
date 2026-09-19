$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    Write-Error 'Create the Python environment first: python -m venv .venv; then install requirements.txt.'
}
& ./.venv/Scripts/python.exe scripts/dev.py
