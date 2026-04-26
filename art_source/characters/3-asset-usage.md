# ③ 角色實裝流程（5 階段）

把編譯好的 spritesheet 接進遊戲，讓 NPC 出現在 zone 中、可走動、可對話。

> 前置：[① 1-asset-creation.md](1-asset-creation.md) 產素材 → [② 2-spritesheet-workflow.md](2-spritesheet-workflow.md) 編譯。

---

## 0. 兩層架構

```
art_source/                              ← 建置輸入（運行時不讀）
└── characters/<id>/
    ├── metadata.json
    ├── rotations/
    └── animations/{idle,walk}/

   ↓ python scripts/generate_spritesheet.py 編譯

game/                                    ← 運行資產
└── assets/
    ├── spritesheet_cache/<id>.png       ← 角色動畫（運行時載這個）
    │   + atlas_config.json
    └── textures/portraits/<id>.png      ← 對話立繪
```

**單一 ID 貫穿**：`chen_ayi` 同時是資料夾名、spritesheet PNG 名、atlas key、portrait PNG 名、.tres 檔名。

---

## 1. 完整流程（以新增「林老師 lin_laoshi」為例）

```
┌─────────────────────────┐
│ Stage 1：交付素材       │  art_source/characters/lin_laoshi/
└──────────┬──────────────┘  game/assets/textures/portraits/lin_laoshi.png
           ▼
┌─────────────────────────┐
│ Stage 2：編譯           │  python scripts/generate_spritesheet.py
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ Stage 3：建 NPCConfig   │  game/src/entities/npcs/resources/lin_laoshi.tres
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ Stage 4：擺進 zone      │  在 Godot 編輯 zone_<name>.tscn
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ Stage 5：F6 測試        │
└─────────────────────────┘
```

---

### Stage 1：交付素材

**Who**：美術組

依 [① 1-asset-creation.md](1-asset-creation.md) 規格生圖、整理：

```
art_source/characters/lin_laoshi/
├── metadata.json
├── rotations/{east,north,south,west}.png
└── animations/
    ├── idle/{east,north,south,west}/frame_*.png
    └── walk/{east,north,south,west}/frame_*.png

game/assets/textures/portraits/lin_laoshi.png   (96×96)
```

---

### Stage 2：編譯 spritesheet

**Who**：任何人

```bash
python scripts/generate_spritesheet.py
```

產出 `game/assets/spritesheet_cache/lin_laoshi.png` + 更新 `atlas_config.json`。冪等，可隨時重跑。

---

### Stage 3：建立 NPCConfig

**Who**：程式組

複製 `game/src/entities/npcs/resources/chen_ayi.tres` 為 `lin_laoshi.tres`，編輯：

```text
[gd_resource type="Resource" script_class="NPCConfig" load_steps=2 format=3]

[ext_resource type="Script" path="res://src/core/classes/NPCConfig.gd" id="1_npc_config"]

[resource]
script = ExtResource("1_npc_config")
npc_id = "lin_laoshi"                       # 同 Stage 1 資料夾名
display_name = "林老師"
display_name_en = "Prof. Lin"
location_zone = "zone_nccu"
system_prompt = "You are 林老師, a literature professor at NCCU..."
personality_tags = ["博學", "親切", "詩詞愛好者"]
base_temperature = 0.75
max_response_tokens = 250
conversation_memory_turns = 6
initial_relationship = 0
```

> **不需要寫 spritesheet 路徑或 portrait 路徑** — `BaseNPC` 與 `DialogueUI` 都會從 `npc_id` 自動推導。

> Player 不需要 .tres — `Player.gd` 內建處理。

---

### Stage 4：擺進 zone

**Who**：場景設計人

在 Godot 開 `game/src/maps/zones/zone_nccu.tscn`：

1. 從檔案系統拖 `src/entities/npcs/BaseNPC.tscn` 進 `YSortRoot`
2. 選中該 NPC，在屬性面板把 `npc_config` 指向 `lin_laoshi.tres`
3. 調整 `position`
4. `Ctrl+S`

---

### Stage 5：F6 測試

| 檢查項 | 預期 |
| --- | --- |
| 角色顯示 | 出現在指定 position |
| 動畫 | 4 方向 idle / walk 切換正確 |
| Y-sort | 角色繞 NPC 背後遮擋正確 |
| 對話 | 走進 InteractArea → 按 E → 對話框出現立繪 + LLM 回覆 |

---

## 2. 故障排除

| 問題 | 原因 | 修正 |
| --- | --- | --- |
| 控制台 `'<id>' not in atlas_config` | spritesheet 沒編譯 | 重跑 Stage 2 |
| 控制台 `Spritesheet missing` | spritesheet PNG 被刪了 | 重跑 Stage 2 |
| 角色顯示為橘色佔位 | npc_id 為空或 NPCConfig 未設 | 檢查 BaseNPC 的 npc_config 屬性、檢查 .tres 的 npc_id 欄位 |
| 對話框立繪空白 | portraits/<id>.png 不存在 | 補上 portrait 檔，命名要對 |
| 撞不到 NPC | BaseNPC 的 collision shape 沒設 | 在 BaseNPC.tscn 設 CollisionShape2D |
| ID 改名後遊戲爆炸 | 6 處 ID 不對齊 | 全文搜尋舊 ID，全部換成新 ID，重跑 Stage 2 |

---

## 3. 設計原則

- **單一 ID 貫穿** — 6 處（資料夾、metadata、spritesheet、atlas key、portrait、.tres）以 `npc_id` 統一
- **Stage 2 冪等** — 隨時可重跑，安全
- **角色自包** — 刪 `art_source/characters/<id>/` + `<id>.tres` + `portraits/<id>.png` + 重跑 Stage 2，該 NPC 從遊戲乾淨消失
- **運行只看編譯產物** — `art_source/` 不會被 Godot import，不影響遊戲打包大小

---

## 4. 程式端 API 速查

```gdscript
# 載入角色 SpriteFrames
var frames: SpriteFrames = SpriteSheetLoader.load_character("chen_ayi")

# 載入對話立繪
var portrait: Texture2D = npc_config.get_portrait()  # 自動讀 portraits/<npc_id>.png
```

實作細節：
- [SpriteSheetLoader.gd](../../game/src/core/classes/SpriteSheetLoader.gd) — atlas_config 解析 + AtlasTexture 切片
- [NPCConfig.gd](../../game/src/core/classes/NPCConfig.gd) — `get_portrait()` 從 npc_id 推路徑
- [BaseNPC.gd](../../game/src/entities/npcs/BaseNPC.gd) — 在 `_ready()` 自動載 spritesheet
- [Player.gd](../../game/src/entities/player/Player.gd) — 同上，PLAYER_ID = "player"
