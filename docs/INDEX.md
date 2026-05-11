# 文檔導覽

《MuzhaRPG》全部文檔的單一入口。**先看這頁，再點進對應主題。**

---

## 🚀 我是新人，從哪開始？

| 你是誰 | 直接看這一份 |
|---|---|
| 想試玩專案 | [README.md](../README.md) — 安裝、啟動、鍵位 |
| 場景設計人（不寫程式） | [docs/scene-design-workflow.md](scene-design-workflow.md) — 一頁速查 |
| 美術 / 生圖人 | [pipeline/README.md](../pipeline/README.md) — Pipeline + Web UI 使用方式 |
| 章節作者 | [docs/chapter-development.md](chapter-development.md) |
| 程式 / 系統設計 | [docs/architecture.md](architecture.md) |
| 對話系統工程師 | [docs/dialogue-architecture.md](dialogue-architecture.md) |

---

## 📖 文檔總清單

### 入口與架構

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [README.md](../README.md) | 322 | 所有人 | 專案總覽、安裝、啟動、鍵位、開發進度 |
| [docs/architecture.md](architecture.md) | 144 | 程式 | 系統架構、autoload 職責、目錄樹、資料流 |
| **docs/INDEX.md**（本檔） | — | 所有人 | 文檔導覽 |

### 場景與美術

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [docs/scene-design-workflow.md](scene-design-workflow.md) | 114 | 場景設計人 | **一句話清單** — 跟 AI 說什麼、怎麼擺場景、提交流程 |
| [docs/tilemapdual-guide.md](tilemapdual-guide.md) | 155 | 場景設計人 / 程式 | TileMapDual addon 設定、地形繪製、Wang 4×4 layout |
| [docs/asset-naming-convention.md](asset-naming-convention.md) | 96 | 美術 / 程式 | 資產命名規則、zone / category tag 規範 |
| [pipeline/README.md](../pipeline/README.md) | 131 | 美術 / 程式 | Pipeline 架構 + CLI orchestrator + Web UI 使用方式 |
| [game/src/maps/README.md](../game/src/maps/README.md) | 116 | 程式 | Maps 目錄結構、Zone 場景標準、新增 zone 流程 |
| [game/src/maps/props/README.md](../game/src/maps/props/README.md) | 106 | 程式 | Prop.gd 契約、collision layer、修改碰撞範圍 |

### 對話與章節

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [docs/dialogue-architecture.md](dialogue-architecture.md) | 272 | 程式 / 章節作者 | 對話混合架構（D 方案）— 三層流程、Schema、Phase 1–3 任務 |
| [docs/chapter-development.md](chapter-development.md) | 286 | 章節作者 | 章節資料夾結構（敘事側 + 程式側）、ChapterConfig、events.gd、新章節步驟 |
| [story/chapters/README.md](../story/chapters/README.md) | 49 | 章節作者 | **敘事側工作區**：draft.md 草稿 + assets.{json,md} 資產清單 |
| [game/src/chapters/chapter_template/README.md](../game/src/chapters/chapter_template/README.md) | 53 | 章節作者 | 程式側範本資料夾速查 |
| [game/src/chapters/chapter_01_arrival/README.md](../game/src/chapters/chapter_01_arrival/README.md) | 23 | 章節作者 | 範例章節（程式側） |

### Runtime / Addons

| 文檔 | 行數 | 給誰看 | 內容 |
|---|---|---|---|
| [llm_engine/config-guide.md](../llm_engine/config-guide.md) | 116 | 系統管理員 | llama-server 設定、模型路徑、CUDA/CPU 切換 |
| [docs/addons.md](addons.md) | 86 | 程式 | 採用 / 未採用 addons 紀錄、引入決策清單 |

### 歷史紀錄

| 位置 | 內容 |
|---|---|
| [docs/archive/](archive/) | 已完成的實作計畫、ADR、retired 設計（MCP server、舊 spritesheet 流程等）。日常開發不用看 |

---

## 🎯 依任務查文檔

| 我要做… | 看這幾份 |
|---|---|
| 加新 prop（樹、路燈） | `scene-design-workflow.md` → `pipeline/README.md` |
| 加新地形 autotile | `scene-design-workflow.md` → `tilemapdual-guide.md` |
| 加新 NPC（含立繪 / 動畫） | `pipeline/README.md`（Web UI Create modal 最快） |
| 在 zone 擺東西 / 塗地 | `scene-design-workflow.md`（一頁就夠） |
| 改 prop 碰撞範圍 | `game/src/maps/props/README.md` |
| 加新 zone | `game/src/maps/README.md` |
| 寫新章節 | `chapter-development.md` → `chapter_template/README.md` |
| 寫 authored 對話 beat | `dialogue-architecture.md` 第 6 節 |
| 寫 NPC 約束 prompt | `dialogue-architecture.md` 第 4–5 節 |
| 改 LLM 模型 / 換 host | `llm_engine/config-guide.md` |
| 引入新 Godot addon | `addons.md` 的決策清單 |
| 命名新資產 | `asset-naming-convention.md` |

---

## 🧭 維護準則

新增 / 修改文檔時：

1. **先想分類** — 是入口、場景美術、對話章節、Runtime，還是該歸 archive？
2. **不重複** — 同一資訊只在一處詳述，其他地方放連結
3. **更新時順手改 INDEX** — 本檔行數、摘要要保持新鮮
4. **每個文檔頂端 1 行說目的** — 「這份是 X 給 Y 看的」
5. **完工的實作計畫進 [archive/](archive/)** — 不要污染主清單

AI agent 的 art-pipeline skill 在 `.claude/skills/art-pipeline/SKILL.md`，與本份 INDEX 互補（AI 用 skill，人類用本 INDEX）。
