$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProjectDir '.local-preview.pid'

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host 'No running VisionBridge local preview was recorded.'
    exit 0
}

$PreviewPid = [int](Get-Content -LiteralPath $PidFile -Raw)
$Process = Get-Process -Id $PreviewPid -ErrorAction SilentlyContinue
if ($Process) {
    Stop-Process -Id $PreviewPid
}
Remove-Item -LiteralPath $PidFile -Force
Write-Host 'VisionBridge local preview stopped.'
