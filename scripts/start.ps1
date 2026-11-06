$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Create .venv with Python 3.12 and install requirements-app.txt first.'
}
$env:GRADIO_ANALYTICS_ENABLED = 'False'
& .venv/Scripts/python.exe app.py
