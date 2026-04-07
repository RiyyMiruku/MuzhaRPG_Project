#!/usr/bin/env bash
# ============================================
#   Muzha RPG - AI Server Launcher (macOS / Linux)
# ============================================

set -euo pipefail

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---- Load config ----
CONFIG_FILE="config.json"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "[ERROR] Config file not found: $CONFIG_FILE"
    exit 1
fi

read_config() {
    python3 -c "
import json, platform
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
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

# ---- Check files ----
if [[ ! -f "$SERVER" ]]; then
    echo "[ERROR] llama-server not found: $SERVER"
    echo ""
    echo "Setup steps:"
    echo "  1. Go to https://github.com/ggml-org/llama.cpp/releases"
    echo "  2. Download the build for your platform (macOS: llama-*-bin-macos-arm64.zip)"
    echo "  3. Extract into ai_engine/engines/"
    echo "  4. Update the binaries path in config.json"
    echo ""
    echo "Or install via Homebrew:"
    echo "  brew install llama.cpp"
    echo "  Then set binaries.macos in config.json to: $(which llama-server 2>/dev/null || echo 'llama-server')"
    exit 1
fi

if [[ ! -f "$MODEL" ]]; then
    echo "[ERROR] Model file not found: $MODEL"
    echo ""
    echo "Setup steps:"
    echo "  1. Go to https://huggingface.co/Qwen/Qwen3.5-0.8B-GGUF"
    echo "  2. Download Qwen3.5-0.8B-Q4_K_M.gguf"
    echo "  3. Place it in ai_engine/models/"
    exit 1
fi

# ---- Ensure executable permission ----
chmod +x "$SERVER"

# ---- Launch server ----
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
