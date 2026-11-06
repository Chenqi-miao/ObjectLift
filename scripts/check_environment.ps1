$ErrorActionPreference = 'Stop'
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) { $dockerExe = $dockerCommand.Source }
else { $dockerExe = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Docker CLI not found.' }
& $dockerExe version
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not ready.' }
& $dockerExe run --rm --gpus all ubuntu:24.04 nvidia-smi
if ($LASTEXITCODE -ne 0) { throw 'Container GPU validation failed.' }
