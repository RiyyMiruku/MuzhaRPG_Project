# 文檔導覽

《MuzhaRPG》全部文檔的單一入口。**先看這頁，再點進對應主題。**

---

## 🚀 我是新人，從哪開始？

| 你是誰 | 直接看這一份 |
|---|---|
| 想試玩專案 | [README.md](../README.md) — 安裝 / 啟動 / 鍵位 |
| 場景設計人（不寫程式） | [docs/scene-design-workflow.md](scene-design-workflow.md) — 一頁速查 |
| 美術 / 生圖人 | [game/assets/textures/environment/1-asset-creation.md](../game/assets/textures/environment/1-asset-creation.md) |
| 章節作者 | [docs/chapter-development.md](chapter-development.md) |
| 程式 / 系統設計 | [docs/architecture.md](architecture.md) |
| 對話系統工程師 | [docs/dialogue-architecture.md](dialogue-architecture.md) |

---

## 📖 文檔總清單（按主題分組）

### 入口與架構（先看這層）

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [README.md](../README.md) | 319 | 所有人 | 專案總覽、安裝、啟動、鍵位、開發進度、各角色入口連結 |
| [docs/architecture.md](architecture.md) | 401 | 程式 | 完整系統架構、autoload 職責、目錄樹、資料流、AI pipeline |
| **docs/INDEX.md**（本文） | — | 所有人 | 文檔導覽（你正在看的這份） |

### 場景與美術（依工作分流）

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [docs/scene-design-workflow.md](scene-design-workflow.md) | 198 | 場景設計人 | **一句話清單** — 跟 AI 說什麼、怎麼擺場景、提交流程 |
| [docs/tilemapdual-guide.md](tilemapdual-guide.md) | 154 | 場景設計人 / 程式 | TileMapDual addon 設定、地形繪製、Pixellab 4×4 範本 |
| [game/assets/textures/environment/1-asset-creation.md](../game/assets/textures/environment/1-asset-creation.md) | 238 | 美術 | Pixellab 設定、命名規範、像素規格 |
| [game/assets/textures/environment/2-scene-design.md](../game/assets/textures/environment/2-scene-design.md) | 277 | 場景設計人 | 詳細 Godot 操作（步驟版，補 scene-design-workflow 的細節） |
| [game/assets/textures/environment/3-ai-prompt.md](../game/assets/textures/environment/3-ai-prompt.md) | 110 | AI 操作員 | 大段 AI prompt 範本（一般用不到，本檔備援） |
| [game/src/maps/README.md](../game/src/maps/README.md) | 120 | 程式 | Maps 目錄結構、Zone 場景標準、新增 zone 流程 |
| [game/src/maps/props/README.md](../game/src/maps/props/README.md) | 104 | 程式 | Prop.gd 契約、collision layer、修改碰撞範圍 |

### 對話與章節系統

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [docs/dialogue-architecture.md](dialogue-architecture.md) | 426 | 程式 / 章節作者 | **對話混合架構（D 方案）** — 三層流程、StoryBeat / NPCProfile / TrustGate / BeatRunner schema、Phase 1-3 任務 |
| [docs/chapter-development.md](chapter-development.md) | 275 | 章節作者 | 章節資料夾結構、ChapterConfig 欄位、events.gd 寫法、新章節步驟 |
| [game/src/chapters/chapter_template/README.md](../game/src/chapters/chapter_template/README.md) | 50 | 章節作者 | 範本資料夾速查（複製來建新章節） |
| [game/src/chapters/chapter_01_arrival/README.md](../game/src/chapters/chapter_01_arrival/README.md) | 23 | 章節作者 | 範例章節摘要 |

### 角色動畫

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [art_source/characters/1-asset-creation.md](../art_source/characters/1-asset-creation.md) | 217 | 角色美術 | NPC 序列圖製作、metadata.json |
| [art_source/characters/2-spritesheet-workflow.md](../art_source/characters/2-spritesheet-workflow.md) | 137 | 角色美術 / 程式 | Spritesheet 編譯流程（generate_spritesheet.py） |
| [art_source/characters/3-asset-usage.md](../art_source/characters/3-asset-usage.md) | 200 | 程式 | 在遊戲中載入角色動畫的 API |

### 自動化與 AI

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [scripts/import-assets-guide.md](../scripts/import-assets-guide.md) | 117 | 美術 / 程式 | `import_assets.py` 用法（TOML manifest 驅動 prop 匯入） |
| [art_source/pipeline/README.md](../art_source/pipeline/README.md) | — | 美術 / 程式 | **Pixellab MCP server 工作流程** — 用 Claude 直接生成角色／autotile／物件，自動下載 + 後處理 |
| [docs/art-pipeline-refactor-plan.md](art-pipeline-refactor-plan.md) | — | 程式 | Pipeline 架構決策 ADR（為什麼自寫 MCP server、各美術類型方法選擇） |
| [ai_engine/config-guide.md](../ai_engine/config-guide.md) | 116 | 系統管理員 | llama-server 設定、模型路徑、CUDA/CPU 切換 |

### Addons 與技術決策

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [docs/addons.md](addons.md) | 84 | 程式 | 採用 / 未採用的 addons 紀錄、引入決策清單 |

---

## 🎯 依任務查文檔

| 我要做... | 看這幾份 |
|---|---|
| 加新 prop（樹、路燈） | `scene-design-workflow.md` → `import-assets-guide.md` |
| 加新地形 (autotile) | `scene-design-workflow.md` → `tilemapdual-guide.md` |
| 在 zone 擺東西 / 塗地 | `scene-design-workflow.md`（一頁就夠） |
| 改 prop 碰撞範圍 | `props/README.md` → 「修改碰撞範圍」段 |
| 加新 NPC（基底） | `chapter-development.md` →（建 NPCConfig.tres） |
| 加新 zone | `maps/README.md` |
| 寫新章節 | `chapter-development.md` → `chapter_template/README.md` |
| 寫 authored 對話 beat | `dialogue-architecture.md` 第 6 節 |
| 寫 NPC 約束 prompt（信任值） | `dialogue-architecture.md` 第 4-5 節 |
| 加新 NPC 立繪 / 動畫 | `art_source/characters/1-asset-creation.md` |
| 改 LLM 模型 / 改 host | `ai_engine/config-guide.md` |
| 引入新 Godot addon | `addons.md` 的決策清單 |

---

## 📐 文檔層級設計（為什麼這樣切）

```
                ┌─────────────────────┐
                │   README.md         │  入口層（必看）
                │   docs/INDEX.md     │
                └──────────┬──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 速查層        │   │ 教學層        │   │ 架構層        │
│ (一句話清單)  │   │ (詳細步驟)    │   │ (技術參考)    │
│               │   │               │   │               │
│ scene-design- │   │ 2-scene-      │   │ architecture  │
│ workflow      │   │ design        │   │               │
│               │   │ chapter-      │   │ dialogue-     │
│ chapter_*/    │   │ development   │   │ architecture  │
│ README        │   │ tilemapdual-  │   │               │
│               │   │ guide         │   │               │
└──────────────┘   └──────────────┘   └──────────────┘
        ▲                  ▲                  ▲
        │                  │                  │
        └──────────────────┴──────────────────┘
                           │
                ┌──────────┴──────────┐
                │  資源/腳本層         │
                │  (附在被引用的       │
                │   程式或目錄旁)      │
                │                     │
                │  scripts/import-*   │
                │  game/src/maps/     │
                │  art_source/        │
                │  ai_engine/         │
                └─────────────────────┘
```

---

## 🧭 維護準則

新增 / 修改文檔時：

1. **先想分類**：是速查、教學、還是架構參考？放對位置
2. **不重複**：同一資訊只在一處詳述，其他地方放連結
3. **更新時順手改 INDEX**：本檔的行數/摘要要保持新鮮
4. **每個文檔頂端 1 行說目的**：「這份是 X 給 Y 看的」
5. **快速命中**：寫文檔時想像讀者在 ctrl+F 找特定字串
