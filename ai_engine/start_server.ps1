$Host.UI.RawUI.WindowTitle = "Muzha RPG - AI Server"

Write-Host "============================================"
Write-Host "  Muzha RPG - AI Server Launcher"
Write-Host "============================================"
Write-Host ""

Set-Location $PSScriptRoot

# ---- 讀取 config.json ----
$ConfigFile = "config.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "[ERROR] 找不到設定檔: $ConfigFile" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$Config = Get-Content $ConfigFile -Raw | ConvertFrom-Json

$Server    = $Config.binaries.windows
$Model     = $Config.model_path
$Port      = $Config.server.port
$GpuLayers = $Config.server.gpu_layers
$CtxSize   = $Config.server.context_size
$Template  = $Config.server.chat_template

# ---- 檢查檔案 ----
if (-not (Test-Path $Server)) {
    Write-Host "[ERROR] 找不到 llama-server 執行檔: $Server" -ForegroundColor Red
    Write-Host ""
    Write-Host "請依照以下步驟安裝："
    Write-Host "  1. 前往 https://github.com/ggml-org/llama.cpp/releases"
    Write-Host "  2. 下載 Windows CUDA 或 CPU 版本"
    Write-Host "  3. 解壓後放入 ai_engine/engines/ 目錄"
    Write-Host "  4. 修改 config.json 中的 binaries.windows 路徑"
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path $Model)) {
    Write-Host "[ERROR] 找不到模型檔案: $Model" -ForegroundColor Red
    Write-Host ""
    Write-Host "請依照以下步驟下載："
    Write-Host "  1. 前往 https://huggingface.co/Qwen/Qwen3.5-0.8B-GGUF"
    Write-Host "  2. 下載 Qwen3.5-0.8B-Q4_K_M.gguf"
    Write-Host "  3. 放入與 llama-server.exe 同一資料夾"
    Read-Host "Press Enter to exit"
    exit 1
}

# ---- 顯示設定 ----
Write-Host "Server:   $Server"
Write-Host "Model:    $Model"
Write-Host "Port:     $Port"
Write-Host "GPU:      $GpuLayers layers"
Write-Host "Context:  $CtxSize"
Write-Host "Template: $Template"
Write-Host ""
Write-Host "Starting..." -ForegroundColor Green
Write-Host "============================================"

# ---- 啟動伺服器 ----
& ".\$Server" -m ".\$Model" --port $Port -ngl $GpuLayers -c $CtxSize --chat-template $Template

Write-Host ""
Write-Host "Server stopped."
Read-Host "Press Enter to exit"
