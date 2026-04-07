#!/usr/bin/env bash
# ============================================
#   Muzha RPG - AI Server Launcher (macOS / Linux)
# ============================================

set -euo pipefail

# 切換到腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---- 設定 ----
CONFIG_FILE="config.json"

# 從 config.json 讀取設定（需要系統內建的 python3）
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "[ERROR] 找不到設定檔: $CONFIG_FILE"
    exit 1
fi

read_config() {
    python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
# 依平台選擇 binary 路徑
import platform
os_key = 'macos' if platform.system() == 'Darwin' else 'linux'
binary = cfg['binaries'].get(os_key, 'llama-server')
print(binary)
print(cfg['model_path'])
print(cfg['server']['port'])
print(cfg['server']['gpu_layers'])
print(cfg['server']['context_size'])
print(cfg['server'].get('chat_template', 'chatml'))
"
}

CONFIG_VALUES=$(read_config)
SERVER=$(echo "$CONFIG_VALUES" | sed -n '1p')
MODEL=$(echo "$CONFIG_VALUES" | sed -n '2p')
PORT=$(echo "$CONFIG_VALUES" | sed -n '3p')
GPU_LAYERS=$(echo "$CONFIG_VALUES" | sed -n '4p')
CTX_SIZE=$(echo "$CONFIG_VALUES" | sed -n '5p')
CHAT_TEMPLATE=$(echo "$CONFIG_VALUES" | sed -n '6p')

echo "============================================"
echo "  Muzha RPG - AI Server Launcher"
echo "============================================"
echo ""
echo "Server:   $SERVER"
echo "Model:    $MODEL"
echo "Port:     $PORT"
echo "GPU:      $GPU_LAYERS layers"
echo "Context:  $CTX_SIZE"
echo "Template: $CHAT_TEMPLATE"
echo ""

# ---- 檢查檔案是否存在 ----
if [[ ! -f "$SERVER" ]]; then
    echo "[ERROR] 找不到 llama-server 執行檔: $SERVER"
    echo ""
    echo "請依照以下步驟安裝："
    echo "  1. 前往 https://github.com/ggml-org/llama.cpp/releases"
    echo "  2. 下載對應平台的版本 (macOS: llama-*-bin-macos-arm64.zip)"
    echo "  3. 解壓後放入 ai_engine/engines/ 目錄"
    echo "  4. 修改 config.json 中的 binaries 路徑"
    echo ""
    echo "或使用 Homebrew 安裝："
    echo "  brew install llama.cpp"
    echo "  然後將 config.json 中的 macos binary 改為: $(which llama-server 2>/dev/null || echo 'llama-server')"
    exit 1
fi

if [[ ! -f "$MODEL" ]]; then
    echo "[ERROR] 找不到模型檔案: $MODEL"
    echo ""
    echo "請依照以下步驟下載："
    echo "  1. 前往 https://huggingface.co/Qwen/Qwen3.5-0.8B-GGUF"
    echo "  2. 下載 Qwen3.5-0.8B-Q4_K_M.gguf"
    echo "  3. 放入與 llama-server 同一資料夾"
    exit 1
fi

# ---- 確保執行權限 ----
chmod +x "$SERVER"

# ---- 啟動伺服器 ----
echo "Starting..."
echo "============================================"

"./$SERVER" \
    -m "./$MODEL" \
    --port "$PORT" \
    -ngl "$GPU_LAYERS" \
    -c "$CTX_SIZE" \
    --chat-template "$CHAT_TEMPLATE"

echo ""
echo "Server stopped."
