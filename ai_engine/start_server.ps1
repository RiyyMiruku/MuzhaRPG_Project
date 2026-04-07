$Host.UI.RawUI.WindowTitle = "Muzha RPG - AI Server"

Write-Host "============================================"
Write-Host "  Muzha RPG - AI Server Launcher"
Write-Host "============================================"
Write-Host ""

Set-Location $PSScriptRoot

# ---- Load config.json ----
$ConfigFile = "config.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "[ERROR] Config file not found: $ConfigFile" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$Config = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json

$Server    = $Config.binaries.windows
$Model     = $Config.model_path
$Port      = $Config.server.port
$GpuLayers = $Config.server.gpu_layers
$CtxSize   = $Config.server.context_size
$Template  = $Config.server.chat_template

# ---- Check files ----
if (-not (Test-Path $Server)) {
    Write-Host "[ERROR] llama-server not found: $Server" -ForegroundColor Red
    Write-Host ""
    Write-Host "Setup steps:"
    Write-Host "  1. Go to https://github.com/ggml-org/llama.cpp/releases"
    Write-Host "  2. Download the Windows CUDA or CPU build"
    Write-Host "  3. Extract into ai_engine/engines/"
    Write-Host "  4. Update binaries.windows in config.json"
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path $Model)) {
    Write-Host "[ERROR] Model file not found: $Model" -ForegroundColor Red
    Write-Host ""
    Write-Host "Setup steps:"
    Write-Host "  1. Go to https://huggingface.co/Qwen/Qwen3.5-0.8B-GGUF"
    Write-Host "  2. Download Qwen3.5-0.8B-Q4_K_M.gguf"
    Write-Host "  3. Place it in ai_engine/models/"
    Read-Host "Press Enter to exit"
    exit 1
}

# ---- Show config ----
Write-Host "Server:   $Server"
Write-Host "Model:    $Model"
Write-Host "Port:     $Port"
Write-Host "GPU:      $GpuLayers layers"
Write-Host "Context:  $CtxSize"
Write-Host "Template: $Template"
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host "============================================"

# ---- Launch server ----
& ".\$Server" -m ".\$Model" --port $Port -ngl $GpuLayers -c $CtxSize --chat-template $Template

Write-Host ""
Write-Host "Server stopped."
Read-Host "Press Enter to exit"
