# 木境傳說 (Project Muzha)

> 一款結合超輕量本地端 LLM 與 2.5D 像素美術的微型開放世界 RPG。
> 帶領玩家穿梭於木柵的巷弄、政大的雨季與指南宮的煙霧中，體驗由 AI 驅動的動態在地故事。

## 📖 故事背景

主角是一名就讀於木柵某大學的學生，剛經歷完地獄般的研究所入學考試，目前正處於焦慮等待放榜的空白期。為了打發時間與平復心情，主角開始在木柵這個既熟悉又陌生的區域漫無目的地探索。

從市場菜販的碎念、道南河濱公園的都市傳說，到貓空茶園的奇妙邂逅。玩家將發現，這裡的每一個 NPC 都有自己的生活軌跡，而主角的選擇與對話，將悄悄改變這個區域的日常。

## ✨ 核心特色

- **2.5D 視覺風格：** 結合 2D 像素角色與擬 3D 高低差場景，呈現木柵的丘陵地形。
- **SLM 動態對話系統：** 內建 Qwen-3.5-0.8B 語言模型，NPC 根據任務進度、位置、時間即時回應。
- **無縫大地圖探索：** Zone Loading 系統，4 個區域（政大、市場、指南宮、河濱）流暢切換。
- **任務與存檔系統：** 事件追蹤、NPC 關係值、任務自動判定、JSON 存讀檔。

## 🛠️ 技術棧

| 元件 | 技術 |
|------|------|
| **遊戲引擎** | Godot 4.x (GDScript) |
| **AI 推論後端** | llama.cpp (Sidecar Server, chatml 模式) |
| **語言模型** | Qwen-3.5-0.8B-Chat (Q4_K_M GGUF, 531MB) |
| **美術工具** | Aseprite (像素繪製), VS Code (程式開發) |
| **版本控制** | Git + Git LFS |
| **平台支援** | Windows (CUDA / CPU) |

## 🚀 快速開始

### 1. Clone 專案

```bash
git clone <repository_url>
git lfs pull
```

### 2. 啟動 AI 伺服器

```powershell
cd ai_engine
.\start_server.ps1
```

看到 `server is listening on http://127.0.0.1:8000` 即成功。

> 若遇到 CUDA 錯誤，編輯 `start_server.ps1` 將 `$GpuLayers` 改為 `0`（CPU 模式）。
> 伺服器設定集中於 `ai_engine/config.json`。

### 3. 測試 AI 連線（可選）

```powershell
python ai_engine/scripts/test_ping.py --full
```

### 4. 安裝 CJK 字型

1. 下載 [Noto Sans TC](https://fonts.google.com/noto/specimen/Noto+Sans+TC)
2. 將 `.otf` 放入 `game/assets/fonts/`

### 5. 開啟 Godot 專案

用 Godot 4 匯入 `game/project.godot`，按 F5 執行。

## 🎮 操作說明

| 按鍵 | 功能 |
|------|------|
| WASD / 方向鍵 | 移動 |
| E | 與 NPC 互動 |
| ESC | 暫停選單 / 關閉面板 |
| M | 地圖（小地圖放大 → 世界地圖） |
| J | 任務日誌 |
| Enter | 發送對話訊息 |

> 所有按鍵可在 ESC → Settings 中自訂。設定存檔於 `user://keybinds.json`。

## 🏗️ 架構總覽

```
Godot Frontend                    AI Backend
┌──────────────────┐    HTTP     ┌─────────────────┐
│ Player           │ ──POST──→  │ llama-server     │
│ NPCs (NPCConfig) │ ←─JSON──  │ Qwen-3.5-0.8B   │
│ DialogueUI       │            │ localhost:8000   │
│ StoryManager     │            └─────────────────┘
│ QuestManager     │
│ UIManager (stack) │
└──────────────────┘
```

核心 Autoload：

| 模組 | 職責 |
|------|------|
| **GameManager** | 遊戲狀態機、存讀檔、伺服器生命週期 |
| **StoryManager** | 區域/事件追蹤、NPC 關係值、遊戲時間、AI context 建構 |
| **AIClient** | HTTP 通訊、payload 組合、回應解析 |
| **QuestManager** | 任務接取/完成判定、前置條件、獎勵發放 |
| **UIManager** | UI 面板堆疊、輸入隔離、暫停協調 |
| **EventBus** | 系統間解耦信號 |

> 詳細架構圖、目錄結構、技術決策請參考 [BLUEPRINT.md](docs/BLUEPRINT.md)。

## 🗺️ 遊戲世界

```
        指南宮 (zone_zhinan)
        [廣師父]
            ↕
政大正門 (zone_nccu) ←→ 木柵市場 (zone_market)
    [中轉區]              [陳阿姨, 王伯伯]
            ↕
      道南河濱 (zone_riverside)
      [釣魚老人]
```

每個 NPC 擁有獨立的 AI 人設（NPCConfig .tres），對話內容根據時間、地點、關係值動態生成。

## 📅 開發進度

### ✅ Phase 1: 基礎建設 — 完成
- [x] Godot 專案初始化 + Autoload 架構
- [x] AIClient HTTP 通訊 + 打字機動畫
- [x] 玩家角色移動 + NPC 互動觸發
- [x] 對話框 UI + AI 回應顯示

### ✅ Phase 2: 大地圖與 NPC — 完成
- [x] ZoneManager 非同步場景切換 + 淡入淡出
- [x] 4 個區域場景 + 區域切換觸發器
- [x] 4 個 NPC（陳阿姨、王伯伯、廣師父、釣魚老人）
- [x] 佔位精靈自動產生系統

### ✅ Phase 3: 任務與存檔 — 完成
- [x] QuestManager + QuestData 資源系統
- [x] 存讀檔系統（JSON, user://saves/）
- [x] 遊戲內時間自動推進
- [x] 事件驅動任務自動完成

### ✅ UI 系統 — 完成
- [x] MainMenu（開始/讀檔/離開）
- [x] HUD（區域名、時間、任務提示）
- [x] LiveMinimap（三層：HUD 小地圖 → 區域放大 → 世界地圖）
- [x] QuestJournal（進行中/已完成任務）
- [x] PauseMenu（存讀檔 + Settings）
- [x] KeybindSettings（可自訂按鍵綁定）
- [x] UIManager 堆疊式面板協調

### 🔜 Phase 4: 美術與音效
- [ ] 像素角色精靈（取代佔位方塊）
- [ ] TileMap 區域美術（取代 ColorRect 背景）
- [ ] 環境音效
- [ ] 全域 CJK 字型 Theme

### 🔜 Phase 5: 打包與發佈
- [ ] 打包腳本（Godot 匯出 + llama.cpp + 模型 → 單一目錄）
- [ ] CPU-only 備用二進位
- [ ] 跨平台測試
- [ ] Steam 發佈準備

## 📋 協作規範

### Git 工作流程

- **主分支**: `main`
- **開發分支**: `develop`
- **特性分支**: `feature/<name>`
- **修復分支**: `bugfix/<name>`

### Commit 規範

```
[TYPE] 簡潔描述

TYPE: feat, fix, docs, style, refactor, perf, test
```

## 📄 許可證

（待定義）

## 👥 聯絡

**Bug 回報**: GitHub Issues
**功能建議**: GitHub Discussions
