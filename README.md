# 木境傳說 (Project Muzha)

> 一款結合超輕量本地端 LLM 與 2.5D 像素美術的微型開放世界 RPG。
> 帶領玩家穿梭於木柵的巷弄、政大的雨季與指南宮的煙霧中，體驗由 AI 驅動的動態在地故事。

## 📖 故事背景 (The Lore)

主角是一名就讀於木柵某大學的學生，剛經歷完地獄般的研究所入學考試，目前正處於焦慮等待放榜的空白期。為了打發時間與平復心情，主角開始在木柵這個既熟悉又陌生的區域漫無目的地探索。

從市場菜販的碎念、道南河濱公園的都市傳說，到貓空茶園的奇妙邂逅。玩家將發現，這裡的每一個 NPC 都有自己的生活軌跡，而主角的選擇與對話，將悄悄改變這個區域的日常。

## ✨ 核心特色 (Features)

- **2.5D 視覺風格：** 採用類似《棕色塵埃 2》的視角，結合 2D 高精細像素角色與 3D/擬 3D 高低差場景，完美呈現木柵的丘陵地形（如指南宮、貓空）。
- **SLM 動態對話系統：** 內建 **Qwen 0.9B (GGUF)** 語言模型。NPC 的對話不再是死板的腳本，而是會根據玩家當前的任務進度、所在位置、甚至遊戲內的時間，給出符合其「在地人設」的即時回應。
- **無縫大地圖探索：** 採用 Zone Loading 系統，將政大周邊、木柵市場、河濱公園與山區進行區塊化管理，提供流暢的探索體驗。

## 🛠️ 技術棧 (Tech Stack)

| 元件            | 技術                                    |
| --------------- | --------------------------------------- |
| **遊戲引擎**    | Godot 4.x (GDScript)                    |
| **AI 推論後端** | `llama.cpp` (Sidecar Server 模式)       |
| **語言模型**    | Qwen-3.5-0.8B-Chat (4-bit 量化 GGUF)    |
| **美術工具**    | Aseprite (像素繪製), VS Code (程式開發) |
| **版本控制**    | Git + Git LFS (管理 .gguf 模型)         |
| **平台支援**    | Windows / Linux / macOS                 |

## 📖 專案概述

## 🏗️ 架構總覽 (Architecture Overview)

本專案採用 **前端 (Godot) + 輕量級在地後端 (llama-server)** 的架構：

1.  **實體層 (Entities)：** 每個 NPC 綁定一個 `NPCConfig.tres` 資源，定義其 System Prompt（例如：「你是木柵市場賣菜的陳阿姨，講話帶有台灣國語...」）。
2.  **狀態層 (StoryManager)：** 記錄玩家解鎖了哪些區域、完成了哪些事件（如：已去過指南宮）。
3.  **通訊層 (AIClient)：** 當玩家與 NPC 互動時，動態組合 `NPCConfig` + `StoryManager 的當下狀態` + `玩家輸入`，透過 HTTP POST 發送給本地端的 `llama-server`。
4.  **表現層 (Dialogue UI)：** 接收 AI 的 Streaming 回應，以打字機效果渲染在遊戲畫面中。

## 📂 目錄結構

```
Muzha_RPG_Project/
├── ai_engine/           # AI 推論引擎獨立系統
│   ├── llama-server.exe # Windows 伺服器
│   ├── llama-server     # Linux/Mac 伺服器
│   ├── models/          # GGUF 模型檔 (Git LFS 管理或手動放置)
│   └── scripts/         # 測試用 Python/Shell 腳本
└── game/                # Godot 4 專案根目錄
    ├── project.godot
    ├── addons/          # 第三方插件
    ├── assets/          # 美術資源 (音效、字體、貼圖)
    └── src/             # 遊戲核心程式碼
        ├── autoload/    # 全域單例 (GameManager, AIClient)
        ├── core/        # 基礎類別與組件系統
        ├── entities/    # 玩家與 NPC
        ├── maps/        # 地圖與區域場景
        └── ui/          # 介面系統
```

## 🚀 開發環境建置 (Setup)

### 1. Clone 專案與 LFS 資源

```bash
git clone <repository_url>
git lfs pull  # 確保下載龐大的 .gguf 模型檔
```

### 2. 配置 AI 引擎

- 確認 `ai_engine/models/` 目錄下有正確的 GGUF 模型檔（路徑設定於 `ai_engine/config.json`）：
  ```
  ai_engine/models/llama-b8583-bin-win-cuda-13.1-x64/Qwen3.5-0.8B-Q4_K_M.gguf
  ```
- 若需調整伺服器 Port、GPU 層數或模型路徑，編輯 `ai_engine/config.json` 即可，無需修改程式碼。
- Godot 啟動時，`GameManager.gd` 會自動在背景喚醒 `llama-server.exe` (Windows) 或 `llama-server` (Linux/macOS)。

### 3. 下載工具與依賴

#### Windows

```powershell
# 下載 Godot 4.x 編輯器
# https://godotengine.org/download

# 下載 Llama.cpp 預編譯版本或自行編譯
# https://github.com/ggerganov/llama.cpp/releases
```

#### Linux / macOS

```bash
# 下載 Godot 4.x 編輯器
# 下載或編譯 llama.cpp
```

### 4. 下載 CJK 字型（必要）

Godot 4 的預設字型不支援中文，需手動安裝。

1. 下載 [Noto Sans CJK TC](https://fonts.google.com/noto/specimen/Noto+Sans+TC)（繁體中文，OFL 授權）
2. 將 `NotoSansCJKtc-Regular.otf` 放置於 `game/assets/fonts/`
3. 在 Godot 編輯器中建立 `game/assets/theme/game_theme.tres`，設定全域預設字型

### 5. 在 Godot 編輯器中開啟

- 使用 Godot 4 匯入 `game/project.godot`。
- 建議配置 VS Code 作為外部編輯器，以獲得最佳的 GDScript 與 AI API 聯調體驗。

## 🧪 快速測試

### 手動測試 AI 伺服器連線

```powershell
# Windows - 啟動 llama.cpp 伺服器
cd ai_engine
.\models\llama-b8583-bin-win-cuda-13.1-x64\llama-server.exe `
  -m models\llama-b8583-bin-win-cuda-13.1-x64\Qwen3.5-0.8B-Q4_K_M.gguf `
  --port 8000 -ngl 20
```

```bash
# Linux/macOS - 啟動 llama.cpp 伺服器
cd ai_engine
./llama-server -m models/Qwen3.5-0.8B-Q4_K_M.gguf --port 8000
```

測試連線：

```bash
python ai_engine/scripts/test_ping.py --host localhost --port 8000 --full
```

## 📚 開發指南 (Development Guide)

### 核心系統結構

| 模組                        | 職責                                           |
| --------------------------- | ---------------------------------------------- |
| **GameManager** (autoload)  | 遊戲狀態管理、存檔系統、全域事件派發           |
| **StoryManager** (autoload) | 任務進度追蹤、故事分支控制、已解鎖區域記錄     |
| **AIClient** (autoload)     | HTTP 客戶端，與本地 llama.cpp 通訊、對話流管理 |

### NPC 與對話系統

- 各 NPC 的 System Prompt 儲存於 `game/src/entities/npcs/resources/` (`.tres` Resource 檔)
- 對話支援 **流式輸出** (Streaming) 與 **打字機動畫**
- NPCConfig 範例結構：
  ```gdscript
  system_prompt: "你是木柵市場賣菜的陳阿姨。講話帶點台灣國語，經常碎念天氣與菜價..."
  name: "陳阿姨"
  location: "zone_market"
  personality_tags: ["親切", "碎念", "在地知識"]
  ```

### 地圖與場景系統

- `src/maps/main_world.tscn`: 世界容器，負責動態加載子區域
- `src/maps/zones/`: 各個區域場景
  - `zone_nccu.tscn`: 政大正門與公車轉運站
  - `zone_market.tscn`: 木柵市場與傳統街道
  - `zone_zhinan.tscn`: 指南宮與貓空茶園
  - `zone_riverside.tscn`: 道南河濱公園

### 玩家角色系統

- `src/entities/player/`: 玩家角色檔案
- 支援 Y-Sort 遮擋、平滑移動、動畫狀態機
- 與環境互動通過 Collision Signal (Hitbox)

## 📅 開發里程碑 (Roadmap)

### ✅ Phase 1: 基礎建設 (Foundation) - [進行中]

- [ ] 建立 2.5D 玩家角色移動與 Y-Sort 遮擋系統
- [ ] 實作 Godot 透過 HTTP 呼叫本地 `llama.cpp` 並顯示對話
- [ ] 完成 AIClient 的流式解析與打字機動畫
- [ ] 建立基礎 UI (對話框、提示框)

### 🔜 Phase 2: 大地圖與在地化 (World Building)

- [ ] 建立第一個測試區域（例如：政大正門口與公車站）
- [ ] 建立 Zone Transition (場景無縫切換) 系統
- [ ] 撰寫 3-5 個核心 NPC 的 System Prompt
- [ ] 實作環境互動系統 (可談話的 NPC、可檢視的物件)

### 🔜 Phase 3: 任務與狀態機 (Progression)

- [ ] 實作 `StoryManager`，讓 AI 能感知玩家的歷史行為
- [ ] 加入結合傳統腳本與 AI 生成的主線任務
- [ ] 建立支線任務動態生成系統
- [ ] 實作存檔與讀檔系統

### 🔜 Phase 4: 打包與部署 (Deployment)

- [ ] 撰寫打包腳本，將 Godot 執行檔與 AI 側車整合為單一目錄
- [ ] 優化 CPU/RAM 資源佔用
- [ ] 跨平台測試 (Windows, Linux, macOS)
- [ ] 準備 Steam 發佈

## 📋 協作規範 (Contributing Guidelines)

### Git 工作流程

- **主分支**: `main` (穩定發佈版本)
- **開發分支**: `develop` (協作與集成)
- **特性分支**: `feature/<feature_name>` (從 `develop` 分支出來)
- **修復分支**: `bugfix/<bug_name>` (從 `develop` 分支出來)
- **文檔分支**: `docs/<doc_name>`

### Commit 規範

```
[TYPE] 簡潔描述 (#ISSUE_NUMBER)

選項的詳細說明 (如果必要)

TYPE: feat, fix, docs, style, refactor, perf, test
```

### Pull Request 流程

1. 確保 commit 訊息清晰、功能獨立
2. 在 `develop` 分支上進行本地測試
3. 提交 PR 前進行代碼檢查與品質驗證
4. 至少一位維護者審核後方可合併

## 🎮 快速測試 NPC 對話

```gdscript
# 在 Godot 控制台測試 AIClient (需啟動 llama.cpp 伺服器)
await AIClient.query(
    system_prompt="你是木柵市場賣菜的陳阿姨",
    user_input="你好，菜怎麼賣？",
    max_tokens=100
)
```

## 📄 許可證

（待定義）

## 👥 聯絡與参與

**開發團隊**: [待補充]  
**Discord 社群**: [待補充]  
**Bug 回報**: GitHub Issues  
**功能建議**: GitHub Discussions
