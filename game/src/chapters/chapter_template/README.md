# 章節範本

> 文檔導覽：[../../../../docs/INDEX.md](../../../../docs/INDEX.md) — **對象**：章節作者。**用途**：建新章節用的範本。
> 系統概念見 [chapter-development.md](../../../../docs/chapter-development.md)；對話寫法見 [dialogue-architecture.md](../../../../docs/dialogue-architecture.md)。

複製整個 `chapter_template/` 資料夾並改名為 `chapter_NN_<short_name>/`，然後依下列步驟設定。

## 結構

```
chapter_NN_<short_name>/
├── README.md               ← 章節故事大綱（給開發者看）
├── chapter.tres            ← ChapterConfig 資源
├── events.gd               ← 章節啟動時執行的腳本（可選）
├── quests/                 ← 任務資源（QuestConfig；未來可加）
├── beats/                  ← Authored 對話 beat（StoryBeat .tres）
├── npcs/                   ← 章節限定 NPCProfile .tres
├── dialogue_overlays/      ← (legacy) npc_overlays 文字片段
└── cutscenes/              ← 章節 cutscene .tscn
```

## 步驟

1. **複製範本**：把整個 `chapter_template/` 資料夾複製為 `chapter_NN_<name>/`（例 `chapter_02_market/`）
2. **編輯 README.md**：寫故事大綱、出場 NPC、主要任務
3. **編輯 chapter.tres**：在 Godot 編輯器中設定 ChapterConfig 屬性
   - chapter_id：與資料夾名一致（例 `ch02_market`）
   - order：排序數字
   - prerequisites：前置章節 ID
   - zones_used / npcs_present
   - npc_overlays：跨章節 NPC 的章節差異片段（陳阿姨等共用 NPC）
4. **（可選）編輯 events.gd**：章節啟動時的事件邏輯（NPC 移動、quest 觸發、信號連接）
5. **新增 beats**：在 `beats/` 放 `<beat_id>.tres`，定義必須一字不差出現的劇情段落
6. **新增 NPCProfiles**：在 `npcs/` 放章節限定 NPC 的 `.tres`（含 trust_revelations / forbidden_until_flag / known_facts）
7. **新增 quests**：把 .tres 拖進 `quests/`，並加進 chapter.tres 的 `quests` 陣列

## 必要欄位

`chapter.tres` 至少要設定：
- `chapter_id`
- `display_name`
- `order`

其餘可選。

## 對話混合架構（重要！）

本專案對話分三類：
- **Authored Beat**（30%）：必須一字不差出現的劇情錨點 → 寫在 `beats/`
- **Constrained AI**（60%）：主要 NPC 日常對話，受 NPCProfile 約束 → 寫在 `npcs/`
- **Free AI**（10%）：路人閒聊 → 用 NPCConfig 即可，無需 NPCProfile

完整設計與寫法見 [dialogue-architecture.md](../../../../docs/dialogue-architecture.md)。
