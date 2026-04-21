$Host.UI.RawUI.WindowTitle = "Muzha RPG - AI Server"

Write-Host "============================================"
Write-Host "  Muzha RPG - AI Server Launcher"
Write-Host "============================================"
Write-Host ""

Set-Location $PSScriptRoot

# ---- Load config (default + personal override) ----
$DefaultConfigFile = "config.default.json"
$UserConfigFile    = "config.json"

if (-not (Test-Path $DefaultConfigFile)) {
    Write-Host "[ERROR] Default config not found: $DefaultConfigFile" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

function Merge-Config {
    param($Base, $Override)
    if ($null -eq $Override) { return $Base }
    if (-not ($Override -is [PSCustomObject]) -or -not ($Base -is [PSCustomObject])) {
        return $Override
    }
    foreach ($prop in $Override.PSObject.Properties) {
        $name = $prop.Name
        if ($null -ne $Base.PSObject.Properties[$name]) {
            $Base.$name = Merge-Config $Base.$name $prop.Value
        } else {
            $Base | Add-Member -NotePropertyName $name -NotePropertyValue $prop.Value
        }
    }
    return $Base
}

$Config = Get-Content $DefaultConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json

if (Test-Path $UserConfigFile) {
    $UserConfig = Get-Content $UserConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $Config = Merge-Config $Config $UserConfig
    Write-Host "Config:   $DefaultConfigFile + $UserConfigFile (personal overrides)"
} else {
    Write-Host "Config:   $DefaultConfigFile (no personal override; copy to $UserConfigFile to customize)"
}

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
    Write-Host "  4. Override binaries.windows in config.json (personal override)"
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
