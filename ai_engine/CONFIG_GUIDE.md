# config.json 參數說明

## 目錄結構

```
ai_engine/
├── config.json          ← 所有設定集中於此
├── engines/             ← 推論引擎執行檔（llama-server 等）
│   └── llama-b8583-bin-win-cuda-13.1-x64/
│       ├── llama-server.exe
│       └── (*.dll 等相依檔案)
├── models/              ← 模型檔案（.gguf），可放多個方便切換
│   ├── Qwen3.5-0.8B-Q4_K_M.gguf
│   └── (其他模型...)
└── scripts/
```

> `engines/` 與 `models/` 分開管理，切換模型只需改 `config.json` 的 `model_path`，不用動引擎資料夾。

## server

| 參數 | 目前值 | 可選值 | 說明 |
|------|--------|--------|------|
| `host` | `"127.0.0.1"` | `"127.0.0.1"` / `"0.0.0.0"` | `127.0.0.1` 僅本機可連線；`0.0.0.0` 允許區網內其他裝置連線 |
| `port` | `8000` | `1024` ~ `65535` | 伺服器監聽埠號，避免與其他服務衝突即可 |
| `context_size` | `2048` | `512` / `1024` / `2048` / `4096` / `8192` | 上下文長度（token 數），越大記憶越長但占用更多 VRAM。本專案對話較短，`2048` 即足夠 |
| `gpu_layers` | `20` | `0` = 純 CPU；`1`~`99` = 部分/全部層卸載至 GPU | 設為 `0` 可在無 GPU 環境運行（速度較慢）。macOS Apple Silicon 建議設 `99`（Metal 全加速）。NVIDIA GPU 視 VRAM 調整，0.8B 模型設 `99` 通常沒問題 |
| `chat_template` | `"chatml"` | `"chatml"` / `"llama2"` / `"mistral"` / `"gemma"` / `"phi3"` | 對話模板格式，需與模型匹配。Qwen 系列使用 `chatml`，更換模型時需一併修改 |
| `startup_timeout_sec` | `30` | `10` ~ `120` | 等待伺服器啟動的逾時秒數。CPU 模式或較慢硬體建議調高至 `60`~`120` |
| `health_check_interval_sec` | `5` | `3` ~ `30` | 遊戲端檢查伺服器存活的間隔秒數 |

## binaries

| 參數 | 目前值 | 說明 |
|------|--------|------|
| `windows` | `"engines/llama-b8583-bin-win-cuda-13.1-x64/llama-server.exe"` | Windows 執行檔路徑（相對於 `ai_engine/`） |
| `linux` | `"llama-server"` | Linux 執行檔路徑，若使用系統安裝的 llama-server 可直接填 `"llama-server"` |
| `macos` | `"llama-server"` | macOS 執行檔路徑，Homebrew 安裝後可填 `"llama-server"`；手動下載則填完整相對路徑如 `"engines/llama-macos-arm64/llama-server"` |

## model_path

| 參數 | 目前值 | 說明 |
|------|--------|------|
| `model_path` | `"models/Qwen3.5-0.8B-Q4_K_M.gguf"` | 模型檔案路徑（相對於 `ai_engine/`）。切換模型時只需改此路徑，並確認 `chat_template` 與新模型匹配 |

## 常見配置範例

### Windows + NVIDIA GPU（預設）

```json
{
  "server": { "gpu_layers": 20, "context_size": 2048 },
  "binaries": { "windows": "engines/llama-b8583-bin-win-cuda-13.1-x64/llama-server.exe" },
  "model_path": "models/Qwen3.5-0.8B-Q4_K_M.gguf"
}
```

### Windows 純 CPU

```json
{
  "server": { "gpu_layers": 0, "context_size": 2048, "startup_timeout_sec": 60 },
  "binaries": { "windows": "engines/llama-cpu-x64/llama-server.exe" },
  "model_path": "models/Qwen3.5-0.8B-Q4_K_M.gguf"
}
```

### macOS Apple Silicon (M1/M2/M3/M4)

```json
{
  "server": { "gpu_layers": 99, "context_size": 2048 },
  "binaries": { "macos": "engines/llama-macos-arm64/llama-server" },
  "model_path": "models/Qwen3.5-0.8B-Q4_K_M.gguf"
}
```

### macOS Homebrew 安裝

```json
{
  "server": { "gpu_layers": 99, "context_size": 2048 },
  "binaries": { "macos": "llama-server" },
  "model_path": "models/Qwen3.5-0.8B-Q4_K_M.gguf"
}
```

### 切換模型範例（換用其他模型測試）

```json
{
  "model_path": "models/gemma-2-2b-Q4_K_M.gguf",
  "server": { "chat_template": "gemma" }
}
```
