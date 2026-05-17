# 文檔導覽

《MuzhaRPG》全部文檔的單一入口。**先看這頁,再點進對應主題。**

---

## 🚀 依角色,讀這幾份就夠

| 角色 | 必讀(2–3 份) | 選讀 |
|---|---|---|
| **試玩專案** | [README.md](../README.md) | — |
| **章節作者** | [chapter-development-manual.md](chapter-development-manual.md) + [dialogue-architecture.md](dialogue-architecture.md) | [chapter-01-scene-automation-plan.md](chapter-01-scene-automation-plan.md) |
| **場景設計人** | [scene-design-workflow.md](scene-design-workflow.md) | [tilemapdual-guide.md](tilemapdual-guide.md) |
| **美術 / 生圖** | [pipeline/README.md](../pipeline/README.md) + [asset-naming-convention.md](asset-naming-convention.md) | [art-pipeline skill](../.claude/skills/art-pipeline/SKILL.md) |
| **程式 / 系統** | [architecture.md](architecture.md) + [godot-modules.md](godot-modules.md) | [dialogue-architecture.md](dialogue-architecture.md) |
| **Runtime 維運** | [llm_engine/config-guide.md](../llm_engine/config-guide.md) | [addons.md](addons.md) |

---

## 📖 文檔總清單

### 入口

| 文檔 | 對象 | 內容 |
|---|---|---|
| [README.md](../README.md) | 所有人 | 專案總覽、安裝、啟動、鍵位、開發進度 |
| **docs/INDEX.md** | 所有人 | 文檔導覽(本檔) |

### 系統架構(程式)

| 文檔 | 對象 | 內容 |
|---|---|---|
| [architecture.md](architecture.md) | 程式 | 系統架構、autoload 職責、目錄樹、資料流 |
| [godot-modules.md](godot-modules.md) | 程式 | **Godot 端模組追蹤表** — autoload / class / scene / UI / addon 含實作狀況 |
| [dialogue-architecture.md](dialogue-architecture.md) | 程式 / 章節作者 | 對話三層架構(Authored / Constrained AI / Free)+ TrustGate / BeatRunner schema |
| [addons.md](addons.md) | 程式 | 已採用 / 評估過 / 不採用的 Godot addon 紀錄 |

### 章節開發(章節作者)

| 文檔 | 對象 | 內容 |
|---|---|---|
| [chapter-development-manual.md](chapter-development-manual.md) | 章節作者 | **操作手冊** — 11 階段流程、人工介入點、修改 cheat sheet、API 速查 |
| [dialogue-architecture.md](dialogue-architecture.md) | 章節作者 | 對話系統實作細節(寫 beat / NPCProfile / cutscene 時的依據) |
| [chapter-01-scene-automation-plan.md](chapter-01-scene-automation-plan.md) | 章節作者 | chapter 1 場景擺位策略(範例,可作模板) |

### 場景與美術

| 文檔 | 對象 | 內容 |
|---|---|---|
| [scene-design-workflow.md](scene-design-workflow.md) | 場景設計人 | **一頁速查** — 跟 AI 對話的指令清單 |
| [tilemapdual-guide.md](tilemapdual-guide.md) | 場景設計 / 程式 | TileMapDual addon、地形繪製、Wang 4×4 layout |
| [asset-naming-convention.md](asset-naming-convention.md) | 美術 / 程式 | 資產命名規則、zone / category tag 規範 |
| [pipeline/README.md](../pipeline/README.md) | 美術 / 程式 | Pipeline 架構 + CLI orchestrator + Web UI 用法 |
| [game/src/maps/README.md](../game/src/maps/README.md) | 程式 | Maps 目錄結構、Zone 場景標準、新增 zone 流程 |
| [game/src/maps/props/README.md](../game/src/maps/props/README.md) | 程式 | Prop.gd 契約、collision layer、改碰撞箱 |

### 章節資料夾(範本 / 範例)

| 文檔 | 對象 | 內容 |
|---|---|---|
| [story/chapters/README.md](../story/chapters/README.md) | 章節作者 | **敘事側工作區** — draft.md / assets.json 規範 |
| [game/src/chapters/chapter_template/README.md](../game/src/chapters/chapter_template/README.md) | 章節作者 | 程式側新章節範本速查 |

### Runtime

| 文檔 | 對象 | 內容 |
|---|---|---|
| [llm_engine/config-guide.md](../llm_engine/config-guide.md) | 系統管理員 | llama-server 設定、模型路徑、CUDA/CPU 切換 |

### 歷史紀錄

| 位置 | 內容 |
|---|---|
| [docs/archive/](archive/) | 已退役的設計 / 計畫 / 過時 ADR。日常開發不用看 |

---

## 🎯 依任務查文檔

| 我要做… | 看這份 |
|---|---|
| 加新 prop / NPC / autotile | [pipeline/README.md](../pipeline/README.md) → Dashboard Create modal |
| 在 zone 擺東西 / 塗地 | [scene-design-workflow.md](scene-design-workflow.md) |
| 改 prop 碰撞範圍 | [game/src/maps/props/README.md](../game/src/maps/props/README.md) |
| 加新 zone | [chapter-development-manual.md](chapter-development-manual.md) 階段 4–6 |
| 寫新章節 | [chapter-development-manual.md](chapter-development-manual.md) 11 階段流程 |
| 寫 authored beat / cutscene | [chapter-development-manual.md](chapter-development-manual.md) 階段 8–9 |
| 寫 NPCProfile + 信任值 | [chapter-development-manual.md](chapter-development-manual.md) 階段 7 + [dialogue-architecture.md](dialogue-architecture.md) §3-4 |
| 改 LLM 模型 / 換 host | [llm_engine/config-guide.md](../llm_engine/config-guide.md) |
| 引入新 Godot addon | [addons.md](addons.md) 決策清單 |
| 命名新資產 | [asset-naming-convention.md](asset-naming-convention.md) |

---

## 🧭 維護準則

新增 / 修改文檔時:

1. **先想分類** — 入口 / 系統架構 / 章節開發 / 場景美術 / Runtime / 歷史紀錄,還是該歸 archive?
2. **不重複** — 同一資訊只在一處詳述,其他地方放連結 + 一句摘要
3. **更新時順手改 INDEX**
4. **每個文檔頂端 1 行說目的** — 「給 X 看的,用途是 Y」
5. **退役的進 [archive/](archive/)** — 並在原始檔加 `[RETIRED yyyy-mm-dd]` header 跟取代來源

AI agent 用 `.claude/skills/` 內 skill;人類用本 INDEX。
