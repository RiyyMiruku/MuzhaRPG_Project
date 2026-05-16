# 章節開發操作手冊

> 文檔導覽:[INDEX](INDEX.md) — **對象**:章節作者 / 程式 / 場景設計人。**用途**:從劇本草稿到可玩章節的完整人工介入點清單與順序。
>
> **配套架構文檔**:[dialogue-architecture.md](dialogue-architecture.md) / [chapter-01-scene-automation-plan.md](chapter-01-scene-automation-plan.md) / [godot-modules.md](godot-modules.md)

---

## 開發階段總覽

```
階段 1:劇本草稿     ──► story/chapters/<slug>/draft.md
       │
階段 2:資產清單     ──► story-asset-extraction skill → assets.json
       │
階段 3:資產生成     ──► art-pipeline orchestrator → game/assets + .tscn
       │
階段 4:Zone YAML    ──► story/chapters/<slug>/zones/...
       │
階段 5:Zone build   ──► scripts/build_zone.py → game/src/maps/zones/*.tscn
       │
階段 6:Godot 微調   ──► editor 內拖傳送點 / NPC 位置 / Bake terrain
       │
階段 7:NPCProfile   ──► game/src/chapters/<slug>/npcs/*.tres
       │
階段 8:Cutscene     ──► game/src/chapters/<slug>/cutscenes/*.tres
       │
階段 9:StoryBeat    ──► game/src/chapters/<slug>/beats/*.tres
       │
階段 10:events.gd   ──► 章節 glue 邏輯,串 cutscene / 完成條件
       │
階段 11:玩測 + 鎖   ──► 在 YAML 加 frozen: true / Godot 按 Lock YAML
```

人類在每一階段都要動手,中間 builder 自動串。沒有任何一步可以跳過。

---

## 階段 1:劇本草稿

**位置**:[`story/chapters/<chapter_slug>/draft.md`](../story/chapters/)

`<chapter_slug>` 命名:`chapter_NN_<short_name>`,例:`chapter_01_arrival`。

**寫什麼**(自由格式 markdown,參考 [chapter_01_arrival/draft.md](../story/chapters/chapter_01_arrival/draft.md)):

- 故事背景(主角是誰、什麼處境)
- 主線劇情(關鍵錨點、揭露順序)
- NPC 群像(每個 NPC 一段:角色定位 / 動機 / 行為模式)
- 通關條件(可量化的判定:某 flag、某對話、某 event)
- 雙時空 / 雙視角的處理(若有)
- 遊玩方式(戰鬥 vs 對話 vs 解謎比重)

**長度建議**:60–100 行。太短後面推不出 beat,太長重點分散。

**人工 commit**:寫完先 commit,作為後續所有資產 / 對話的 source of truth。

---

## 階段 2:資產清單

**指令**:在 Claude Code 輸入 `/story-asset-extraction` 或直接讓 AI 看 draft.md。

**輸出**:[`story/chapters/<slug>/assets.json`](../story/chapters/chapter_01_arrival/assets.json) +(可選)`assets.md`

包含四類:
- `moving_npcs`:8 向 + walk(`lin_siqian` 等主要 NPC)
- `static_npcs`:4 向僅 idle(路人、佈景 NPC)
- `iso_props`:單格物件(藥櫃、燈籠、攤位)
- `buildings`:大型 iso 建築立面
- `tilesets`:autotile 地形材質

每筆含 `name` / `description`(送給 Pixellab 的英文 prompt)/ `zone` / `category` / 必要時 `size`、`width`/`height`、`view`、`proportions`。

**人工檢查點**:
- 名稱遵守 regex `^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`
- `description` 是英文(Pixellab 不吃中文)
- 風格詞統一(`taiwanese`, `traditional`, `1983` 等)

---

## 階段 3:資產生成

**位置**:[Dashboard](http://localhost:8765)(`uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765`)

**動作**:
1. 啟動 dashboard → 對每筆 assets.json 條目按「Create」
2. Backend fire-and-forget 跑 Pixellab API(10–30 分鐘 / 角色)
3. 完成後 orchestrator 的 `import_to_godot` 階段自動將:
   - PNG 複製到 `game/assets/textures/{characters,props,tilesets}/`
   - 產出 `game/src/maps/props/<name>.tscn`(prop 才有)
   - 產出 `game/assets/textures/characters/<name>.{png,json}`(NPC spritesheet)

**人工檢查點**:
- 視覺驗收:dashboard 每個 asset 詳細頁能看到產出 PNG
- 不滿意 → 同詳細頁按 Remake(改 prompt / kind / view)
- Pixellab 網站手動編輯(mirror / 重 trigger)後 → 按 Sync from Pixellab 拉回

詳見 [art-pipeline skill](../.claude/skills/art-pipeline/SKILL.md)。

---

## 階段 4:Zone YAML

**位置**:[`story/chapters/<slug>/zones/`](../story/chapters/chapter_01_arrival/zones/)

兩種結構:

**單時空 zone**(只有一個版本):
```
zones/<slug>.yaml
```

**Hybrid era zone**(同地點兩時空):
```
zones/<slug>/
  ├── 1983.yaml      # era: "1983"
  └── modern.yaml    # era: "modern"
```

**最小 YAML**(以 `apartment_muzha.yaml` 為例):
```yaml
zone: zone_apartment_muzha            # Zones.ALL 的 key
label: "木柵老公寓"
size: [22, 17]                        # iso 格,中心 (0,0)

tilemap:
  atlas: market_concrete_tile         # game/assets/textures/tilesets/<atlas>.png
  terrain: 1                          # 1 = FG(全填)
  fill: rect

props:
  - id: id_card_old                   # 對應 props/id_card_old.tscn
    anchor: center                    # 5 種:center / north_wall / south_wall / east_wall / west_wall / entrance / relative_to(X)
    offset: [0, 0]                    # 格單位

  - id: photograph_old
    anchor: relative_to(id_card_old)
    offset: [1, 0]

npcs:
  - id: lin_rongchang                 # 對應 NPCProfile (階段 7)或 fallback Sprite2D
    anchor: relative_to(shop_counter_wood)
    offset: [0, -1]

transitions:
  - target_zone: zone_market          # 必須在 Zones.ALL 註冊
    entry_point: from_apartment       # target zone 的 entry_points key
    anchor: south_wall
    offset: [0, 1]
    rename: ToMarket

player_spawn:
  anchor: south_wall
  offset: [0, -1]
```

**人工動作**:
1. 從 draft.md + assets.json 推演每個 zone 應該有哪些 prop / NPC / 出口
2. 寫 YAML(Claude 可代寫初稿)
3. 跟 `Zones.ALL` 對齊:每個 `target_zone` / `entry_point` 必須在 [Zones.gd](../game/src/core/classes/Zones.gd) 註冊

**新增 Zone 時還要做**:
- 開 [Zones.gd](../game/src/core/classes/Zones.gd),在 `ALL` dict 加 entry:`scene` 路徑 / `world_pos` / `entry_points` / `connects_to`

---

## 階段 5:Zone build

**指令**(repo root):
```bash
uv run python scripts/build_zone.py <name> [--force]
```

`<name>` 是 zone slug(`pharmacy_backyard`)或 hybrid folder(`pharmacy`)。

**Builder 做的事**:
- 合併 hybrid 多份 YAML → 同一 `.tscn`,prop/npc 加 `groups=["era_<era>"]`
- 解析 anchor / offset → iso 座標
- emit:
  - Player + Camera2D + PhantomCameraHost + DefaultCam(GLUED follow Player)
  - EraTint(CanvasModulate,hybrid only)
  - TileMapDual + 16-tile Wang autotile TileSet(inline sub_resource)
  - terrain_cells `Array[Vector2i]`(待 Godot 按 Bake terrain 一鍵塗)
  - Prop / NPC instances(BaseNPC 若有 NPCProfile,否則 Sprite2D placeholder)
  - ZoneTransitionArea instances(每 transition)
  - yaml_paths(供 zone_baker.gd 的 Lock/Unlock 按鈕用)

**人工 commit**:zone .tscn 通常一起 commit。

---

## 階段 6:Godot 微調

**位置**:`game/src/maps/zones/zone_<slug>.tscn`(Godot editor 內開)

**必做**(每個 zone 一次):
1. 選 root → Inspector 找 4 個 `@tool` 按鈕:
   - **Bake terrain** ← 按下,把 `terrain_cells` 塗進 TileMapDual
2. Ctrl+S 存檔

**選做**(看視覺微調):
- 拖 ZoneTransitionArea 對準鐵門 / 路口
- 拖 NPC / prop 對準櫃台 / 攤位邊緣
- 改 ZoneTransitionArea 內 CollisionShape2D 的 size(預設 40×20 不一定對)

**完成後**:
3. 選 root → 按 **Lock YAML (frozen: true)** → builder 之後 refuse 重蓋

**不可改的東西**(在 prop 自己的 .tscn,不是 zone):
- 個別 prop 的碰撞箱大小 → 改 `art_source/objects/<name>/asset.json` 的 `collision` 然後 Dashboard 重 `import_to_godot`,或直接編輯 `game/src/maps/props/<name>.tscn`

---

## 階段 7:NPCProfile

**位置**:`game/src/chapters/<slug>/npcs/<npc_id>.tres`

**為什麼放章節資料夾而不是 entities/npcs/definitions/**:
- `entities/npcs/definitions/` = 跨章節共用基底 NPC(陳阿姨等)
- `chapters/<slug>/npcs/` = 該章節限定的 NPC(`lin_rongchang` 只在 chapter 1)

Builder `resolve_npc()` 兩處都搜,先共用後章節。

**.tres 內容**(以 [lin_rongchang.tres](../game/src/chapters/chapter_01_arrival/npcs/lin_rongchang.tres) 為例):

```
[gd_resource type="Resource" script_class="NPCProfile" load_steps=2 format=3]

[ext_resource type="Script" path="res://src/core/classes/NPCProfile.gd" id="1_profile"]

[resource]
script = ExtResource("1_profile")
npc_id = "lin_rongchang"
display_name = "林榮昌"
location_zone = "zone_pharmacy"
system_prompt = "你是林榮昌,46歲,..."   # NPC 人格 + 限制 + 風格
personality_tags = Array[String](["沉默", "守護", ...])
base_temperature = 0.6                  # 越低越穩定
max_response_tokens = 200
era = "1983"                            # 1983 / modern / any
trust_revelations = [{
  "threshold": 0, "topics": ["藥行日常", "中藥知識"]
}, {
  "threshold": 60, "topics": ["承認家裡有上鎖房間"]
}]
forbidden_until_flag = {
  "林榮華": "ending_finale_active"      # flag 沒 true 之前 AI 不能說這個詞
}
known_facts = Array[String]([
  "我是榮昌中藥行第三代",
  ...
])
personality_voice = "短句為主,語氣穩重..."
```

**人工檢查點**:
- `npc_id` 必須跟 spritesheet 檔名 / asset.json `name` / YAML 引用一致
- `system_prompt` 寫繁中,2-3 句設定 + 一句限制(回應長度 / 風格)
- `trust_revelations` 至少 3 段門檻(0 / 30 / 60),最後一段對應「最深秘密」
- `forbidden_until_flag` 包含主線揭露相關的關鍵字
- `era` 對應 zone hybrid era,讓未來 EraManager 可以 NPC era 過濾

---

## 階段 8:Cutscene

**位置**:`game/src/chapters/<slug>/cutscenes/<id>.tres`

**何時用 cutscene 而不是 beat**:
- 需要鏡頭移動(zoom 到塗黑全家福)
- 需要時空切換(era_switch)
- 純旁白沒對話對手(narrator 描述)

**支援 ops**(見 [Cutscene.gd](../game/src/core/classes/Cutscene.gd) 註解):
```
{"op": "line", "speaker": "narrator", "text": "..."}
{"op": "wait", "seconds": 0.5}
{"op": "camera_to", "target_path": "YSortRoot/family_photo_blacked_modern",
                    "zoom": [6.0, 6.0], "duration": 1.5}
{"op": "restore_camera"}
{"op": "set_flag", "name": "saw_blacked_photo", "value": true}
{"op": "emit_event", "name": "ch1_first_travel_done"}
{"op": "era_switch", "era": "1983"}
```

**範例**:[ch1_open_iron_door.tres](../game/src/chapters/chapter_01_arrival/cutscenes/ch1_open_iron_door.tres)

**人工 touch points**:
- `target_path` 必須對應 zone .tscn 內實際存在的節點(注意 hybrid zone 的 era suffix:`LinRongchang_1983` / `family_photo_blacked_modern`)
- camera zoom 越大畫面越近;3.0 是預設,5–7 適合特寫單一 prop
- duration 0.5–1.5s 之間最自然

---

## 階段 9:StoryBeat

**位置**:`game/src/chapters/<slug>/beats/<beat_id>.tres`

**何時用 beat 而不是 AI 自由對話**:
- 必須一字不差的劇情錨點(自我介紹、揭露真相)
- 帶分支選項影響 flag
- 主線進度判定的對話節點

**.tres 內容**(以 [ch1_meet_lin_rongchang.tres](../game/src/chapters/chapter_01_arrival/beats/ch1_meet_lin_rongchang.tres) 為例):

```
[resource]
script = ExtResource("1_beat_script")
beat_id = "ch1_meet_lin_rongchang"

# ── 觸發條件(AND) ──
trigger_flags = { "first_time_traveled": true }
trigger_npc_id = "lin_rongchang"      # 跟此 NPC 互動才觸發
trigger_zone = ""                      # 任何 zone(空 = 不限)
trigger_event = ""                     # (可選)某 event 完成才觸發

# ── 對白(順序播放) ──
dialogue_lines = [
  { "speaker": "林榮昌", "text": "你誰啊?" },
  { "speaker": "narrator", "text": "(阿謙腦中飛快地想著該怎麼解釋。)" },
  ...
]

# ── 結尾選項(可空) ──
choices = [{
  "text": "(點頭,默默開始工作)",
  "set_flags": { "lin_rongchang_accepted_fake_identity": true }
}]

# ── 完成後副作用 ──
on_complete_flags = { "ch1_beat_meet_lin_rongchang_done": true }
on_complete_event = "ch1_started_living_in_pharmacy"
```

**人工檢查點**:
- 每個 beat 結束務必 set 一個 flag(防重觸發,BeatRunner 用 `beat_done_<id>` 自動記錄)
- 後續 beat 用前面的 `on_complete_event` / `on_complete_flags` 做 trigger,串成 quest 鏈
- 對白盡量短,每個 line 1–3 句即可

---

## 階段 10:events.gd 章節 glue

**位置**:[`game/src/chapters/<slug>/events.gd`](../game/src/chapters/chapter_01_arrival/events.gd)

**職責**(不能被 beat / cutscene .tres 表達的 cross-cutting 邏輯):
1. zone 進入時自動觸發 cutscene
2. 多個 flag 組合判定 → emit 額外 event
3. 章節通關條件偵測 → `ChapterManager.complete_current()`

**範例**:
```gdscript
extends RefCounted

const OPEN_IRON_DOOR_CUTSCENE: String = (
    "res://src/chapters/chapter_01_arrival/cutscenes/ch1_open_iron_door.tres"
)

func register(_manager: Node) -> void:
    EventBus.zone_loaded.connect(_on_zone_loaded)
    StoryManager.event_recorded.connect(_on_event_recorded)

func unregister(_manager: Node) -> void:
    ...

func _on_zone_loaded(zone_id: String) -> void:
    if (
        zone_id == "zone_pharmacy"
        and EraManager.current_era == "modern"
        and not StoryManager.completed_events.has("ch1_first_travel_done")
    ):
        EventBus.cutscene_requested.emit(OPEN_IRON_DOOR_CUTSCENE)

func _on_event_recorded(event_id: String) -> void:
    if event_id == "ch1_finale_said_brother_name":
        StoryManager.player_flags["chapter_completed_ch01_arrival"] = true
        ChapterManager.complete_current()
```

**人工檢查點**:
- 每個 zone-entry-trigger 必須帶「沒做過」guard(避免重複)
- 通關條件用 `event_recorded` 不要用 `flag_changed`(更精準)

---

## 階段 11:玩測 + Lock

**順序**:
1. F5 啟動,玩測整個章節 happy path(從 STARTING 走到通關)
2. 玩測 alternative path(故意觸發 trust 低的對話、故意走錯)
3. 邊測邊調 NPCProfile prompt(trust_revelations 範圍 / forbidden 字 / system_prompt 風格)
4. 每個 zone 都在 Godot 微調過 → 選 root → **Lock YAML**(builder 之後 refuse 重蓋)
5. Commit 全部變動

---

## 修改細節:常見場景 cheat sheet

| 要改什麼 | 改哪裡 | 後續動作 |
|---|---|---|
| 新增一個 prop 到 zone | YAML `props:` 加一條 | `build_zone.py <slug> --force` |
| 改 NPC 站位 | Godot editor 拖 → save | 無(直接在 .tscn) |
| 改 ZoneTransitionArea 位置 | Godot editor 拖 → save | 無 |
| 改 NPC 信任值門檻 | NPCProfile.tres `trust_revelations` | 無(Resource 直接被讀) |
| 加新的禁忌詞 | NPCProfile.tres `forbidden_until_flag` | 無 |
| 改某 beat 對白 | StoryBeat.tres `dialogue_lines` | 無;若已玩過要清 save 重玩 |
| 新增章節錨點 cutscene | 新 .tres in cutscenes/ + events.gd 加 trigger | 無 |
| 改 zone 大小 | YAML `size:` | `--force` 重 build,Bake terrain |
| 改 era 切換 tint 顏色 | EraManager.gd `TINT_PRESETS` | 無 |
| 新增 zone | 加 YAML + 加 Zones.ALL entry + build | 連接 zone 的 `connects_to` 也要更新 |
| 改章節 NPC 描述 | ChapterConfig.npc_overlays | 無 |
| LLM 講話風格不對 | NPCProfile.system_prompt + personality_voice | 重新對話測試 |
| LLM 講了禁忌詞 | TrustGate.filter_forbidden 已 post-process 過濾;若仍漏 → 加進 forbidden_until_flag | 無 |

---

## 章節資料夾完整結構速查

```
story/chapters/<slug>/
├── README.md             ← 章節簡介(敘事側)
├── draft.md              ← 階段 1 草稿
├── assets.json           ← 階段 2 資產清單
├── assets.md             ← (可選)資產 markdown 註解
├── notes/                ← (可選)雜記
└── zones/                ← 階段 4 YAML
    ├── <hybrid_zone>/
    │   ├── 1983.yaml
    │   └── modern.yaml
    └── <flat_zone>.yaml

game/src/chapters/<slug>/
├── chapter.tres          ← ChapterConfig(章節 metadata + npc_overlays)
├── events.gd             ← 階段 10 章節 glue
├── npcs/                 ← 階段 7 NPCProfile
│   └── *.tres
├── beats/                ← 階段 9 StoryBeat
│   └── *.tres
├── cutscenes/            ← 階段 8 Cutscene
│   └── *.tres
└── quests/               ← (可選)QuestData
    └── *.tres
```

---

## 相關文件

- [docs/dialogue-architecture.md](dialogue-architecture.md) — 對話系統內部設計(TrustGate / BeatRunner / 三層架構)
- [docs/chapter-01-scene-automation-plan.md](chapter-01-scene-automation-plan.md) — chapter 1 場景擺位策略
- [docs/godot-modules.md](godot-modules.md) — Godot 端模組追蹤表
- [art-pipeline skill](../.claude/skills/art-pipeline/SKILL.md) — 美術 pipeline 細節
- [chapter_template/](../game/src/chapters/chapter_template/) — 新章節範本
