$ErrorActionPreference = 'Stop'

$PidFile = Join-Path $PSScriptRoot '.fullstack-preview.pid'
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Output 'VisionBridge preview is not running.'
    exit 0
}

$PreviewPid = [int](Get-Content -LiteralPath $PidFile -Encoding ASCII)
$Process = Get-Process -Id $PreviewPid -ErrorAction SilentlyContinue
if ($Process) { Stop-Process -Id $PreviewPid -Force }
Remove-Item -LiteralPath $PidFile -Force
Write-Output 'VisionBridge full-stack preview stopped.'
