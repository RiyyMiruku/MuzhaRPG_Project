$Host.UI.RawUI.WindowTitle = "Muzha RPG - AI Server"

Write-Host "============================================"
Write-Host "  Muzha RPG - AI Server Launcher"
Write-Host "============================================"
Write-Host ""

Set-Location $PSScriptRoot

$Server = "models\llama-b8583-bin-win-cuda-13.1-x64\llama-server.exe"
$Model  = "models\llama-b8583-bin-win-cuda-13.1-x64\Qwen3.5-0.8B-Q4_K_M.gguf"
$Port   = 8000
$GpuLayers = 20
$CtxSize = 2048

if (-not (Test-Path $Server)) {
    Write-Host "[ERROR] llama-server.exe not found: $Server" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path $Model)) {
    Write-Host "[ERROR] Model file not found: $Model" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Server: $Server"
Write-Host "Model:  $Model"
Write-Host "Port:   $Port"
Write-Host "GPU:    $GpuLayers layers"
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host "============================================"

& ".\$Server" -m ".\$Model" --port $Port -ngl $GpuLayers -c $CtxSize --chat-template chatml

Write-Host ""
Write-Host "Server stopped."
Read-Host "Press Enter to exit"
