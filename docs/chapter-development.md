# 章節開發指南

《MuzhaRPG》以章節制推進故事。本文說明章節系統架構、新增章節流程、以及如何在章節中改變 NPC 行為。

---

## 1. 為什麼分章節？

把「會復用的素材」與「章節獨有的內容」分開：

```
全域資源池（永遠存在）          章節資料夾（差異層）
───────────────────────────────────────────────────────
角色 sprite / 立繪              章節故事腳本
Tileset / autotile / props      章節獨有任務
Zone 場景（共用地理）           章節 NPC 對話差異
NPCConfig 基底人設              章節限定 NPC（若有）
                                Cutscene
```

→ 改一張陳阿姨的圖只動一個地方；改第 5 章陳阿姨的對話傾向只動 chapter_05/。

---

## 2. 系統架構

```
       NPCConfig (基底)            ChapterConfig (差異)        StoryManager (狀態)
       ────────────────             ─────────────────           ─────────────────
       npc_id = "chen_ayi"          npc_overlays[chen_ayi]      relationships[chen_ayi]
       system_prompt = "..."        = "你不認識玩家"             = 0
       (永遠不變)                    (隨章節變)                  (隨遊玩變)
                  │                          │                          │
                  └──────────────┬───────────┴──────────────────────────┘
                                 ▼
                          AIClient.query()
                          組合三層成完整 system prompt
                                 │
                                 ▼
                              LLM API
```

---

## 3. 檔案結構

```
game/src/
├── core/classes/
│   └── ChapterConfig.gd               ← Resource 類別定義
├── autoload/
│   └── ChapterManager.gd              ← 全域單例（autoload）
├── entities/npcs/
│   └── definitions/                   ← NPC 基底設定（不分章節）
│       ├── chen_ayi.tres
│       ├── master_guang.tres
│       └── ...
└── chapters/
    ├── chapter_template/              ← 範本：複製這個建新章節
    │   ├── README.md
    │   ├── chapter.tres
    │   ├── events.gd
    │   ├── quests/
    │   ├── dialogue_overlays/
    │   └── cutscenes/
    ├── chapter_01_arrival/            ← 範例章節（已建立）
    │   └── ... (同上結構，已填內容)
    ├── chapter_02_xxx/
    └── chapter_03_xxx/
```

---

## 4. 新增章節流程

### Step 1：複製範本

```bash
cp -r game/src/chapters/chapter_template game/src/chapters/chapter_NN_<short_name>
```

例：`chapter_02_market`、`chapter_05_temple_visit`。

### Step 2：填 README.md

寫故事大綱、出場 NPC、主要任務、完成條件 — 給其他開發者看。

### Step 3：在 Godot 編輯 chapter.tres

打開 `chapter.tres`，在屬性面板填：

| 欄位 | 範例 | 說明 |
| --- | --- | --- |
| chapter_id | `ch02_market` | 唯一 ID（建議 `ch<NN>_<name>`） |
| display_name | `市場初探` | 中文顯示名 |
| order | `2` | 排序，1=第一章 |
| prerequisites | `["ch01_arrival"]` | 必須先完成的章節 |
| zones_used | `["zone_market"]` | 本章用到的 zone |
| npcs_present | `["chen_ayi", "wang_bobo"]` | 本章出場 NPC |
| npc_overlays | `{"chen_ayi": "..."}` | NPC 章節差異片段 |
| events_script | `events.gd` | 章節事件腳本 |
| quests | `[...]` | quest 資源（可空） |
| completion_flags | `["bought_first_meal"]` | 觸發後完成本章 |
| synopsis | `"..."` | 簡短摘要 |

### Step 4：寫 events.gd（可選）

如需章節啟動時做事（連接 signal、註冊 quest、觸發 cutscene），編輯 `events.gd`：

```gdscript
extends RefCounted

func register(_manager: Node) -> void:
    StoryManager.event_recorded.connect(_on_event)

func unregister(_manager: Node) -> void:
    if StoryManager.event_recorded.is_connected(_on_event):
        StoryManager.event_recorded.disconnect(_on_event)

func _on_event(event_id: String) -> void:
    if event_id == "bought_first_meal":
        StoryManager.player_flags["chapter_completed_ch02_market"] = true
        ChapterManager.complete_current()
```

### Step 5：啟動章節

由 `GameManager` 或新遊戲流程呼叫：

```gdscript
ChapterManager.start_chapter("ch02_market")
```

---

## 5. NPC 章節差異 — 怎麼運作？

當玩家對 NPC 按 E：

```
BaseNPC.interact()
  → AIClient.query(npc_config, user_input, context)
      → 組合 system prompt：
          npc_config.system_prompt              ← 基底人設
          + ChapterManager.get_npc_overlay(id)  ← 章節差異片段
          + context (時間、好感度、近期事件)    ← 動態狀態
      → 送 LLM API
```

**範例：陳阿姨在不同章節的 prompt**

第 1 章（chapter_01_arrival 的 npc_overlays）：
```
You are 陳阿姨, a vegetable vendor at Muzha Market...
[章節背景] （玩家剛搬來木柵第一天，你不認識他...）
[時間]：14:30，下午
[好感度]：0（陌生人）
```
→ 陳阿姨會說：「歡迎光臨～你是新來的學生嗎？」

第 5 章（npc_overlays 改成「你已認識玩家半年」）：
```
You are 陳阿姨, a vegetable vendor at Muzha Market...
[章節背景] （你已認識玩家半年，知道他是政大研究生，常來買菜）
[時間]：18:00，傍晚
[好感度]：35
```
→ 陳阿姨會說：「啊小張你今天又來啦！學校還忙不忙？」

---

## 6. 設計原則

- **角色基底永遠不變** — `chen_ayi.tres` 不為任何章節改動
- **章節差異用 overlay 注入** — 不複製整份 NPCConfig
- **狀態 = 章節 × 玩家行為** — Chapter 提供章節背景，StoryManager 提供具體狀態
- **章節腳本要對稱 register / unregister** — 避免章節切換後殘留 signal 連接
- **完成條件用 flag** — 不要硬編 quest 名，讓多種方式都能觸發章節推進

---

## 7. 程式端 API 速查

```gdscript
# 取當前章節
var chapter: ChapterConfig = ChapterManager.current()

# 切章節
ChapterManager.start_chapter("ch02_market")

# 完成當前章節（自動進下一章）
ChapterManager.complete_current()

# 章節是否包含某 NPC
ChapterManager.is_npc_active("chen_ayi")

# NPC 在當前章節的差異片段（AIClient 自動用）
var overlay: String = ChapterManager.get_npc_overlay("chen_ayi")

# 列出所有章節（按 order 排序）
var all: Array = ChapterManager.list_all()
```

---

## 8. 相關檔案

- 類別定義：[ChapterConfig.gd](../game/src/core/classes/ChapterConfig.gd)
- Autoload：[ChapterManager.gd](../game/src/autoload/ChapterManager.gd)
- AIClient prompt 組合：[AIClient.gd](../game/src/autoload/AIClient.gd)
- 範本：[chapter_template/](../game/src/chapters/chapter_template/)
- 範例章節：[chapter_01_arrival/](../game/src/chapters/chapter_01_arrival/)
