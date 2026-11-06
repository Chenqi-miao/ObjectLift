param([string]$Proxy = 'http://127.0.0.1:7890')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$vendorPath = Join-Path $projectRoot 'vendor'
New-Item -ItemType Directory -Force -Path $vendorPath | Out-Null
$archivePath = Join-Path $vendorPath 'triposr-download.zip'
$curlArgs = @('--http1.1', '--retry', '5', '--retry-all-errors', '--retry-delay', '3',
    '--connect-timeout', '30', '--max-time', '900', '-L', '--fail',
    'https://codeload.github.com/VAST-AI-Research/TripoSR/zip/refs/heads/main', '-o', $archivePath)
if ($Proxy) { $curlArgs = @('--proxy', $Proxy) + $curlArgs }
& curl.exe @curlArgs
if ($LASTEXITCODE -ne 0) { throw 'Source download failed; archive may be incomplete.' }
if (Test-Path (Join-Path $vendorPath 'TripoSR-main')) {
    throw 'TripoSR-main already exists; keeping existing source untouched.'
}
Expand-Archive -LiteralPath $archivePath -DestinationPath $vendorPath
Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
Write-Host 'Downloaded upstream main snapshot. Record its hash before building.'
