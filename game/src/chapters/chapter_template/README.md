# 章節範本

複製整個 `chapter_template/` 資料夾並改名為 `chapter_NN_<short_name>/`，然後依下列步驟設定。

## 結構

```
chapter_NN_<short_name>/
├── README.md               ← 章節故事大綱（給開發者看）
├── chapter.tres            ← ChapterConfig 資源
├── events.gd               ← 章節啟動時執行的腳本（可選）
├── quests/                 ← 任務資源（QuestConfig；未來可加）
├── dialogue_overlays/      ← 對話覆寫（暫未使用，預留）
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
   - npc_overlays：NPC 對話差異片段
4. **（可選）編輯 events.gd**：章節啟動時的事件邏輯（NPC 移動、quest 觸發、信號連接）
5. **新增 quests**：把 .tres 拖進 `quests/`，並加進 chapter.tres 的 `quests` 陣列

## 必要欄位

`chapter.tres` 至少要設定：
- `chapter_id`
- `display_name`
- `order`

其餘可選。
