# 對話系統：Authored Beat + AI 混合架構

> 文檔導覽：[INDEX](INDEX.md) — **對象**：程式 / 章節作者。**用途**：D 方案完整設計、新類別 schema、Phase 1-3 實作任務。

決定於 2026-04-28，採「**自寫 StoryBeat + 擴充 DialogueUI**」（D 方案，比較見 [addons.md](addons.md)）。

---

## 1. 三層對話

| 類別 | 比例 | 性質 | 由誰生成 |
|---|---|---|---|
| **Authored Beat** | ~30% | 主線錨點，必須一字不差 | 手寫 `.tres` |
| **Constrained AI** | ~60% | 主要 NPC 日常，受人格 + trust + flags 約束 | AIClient + TrustGate |
| **Free AI** | ~10% | 路人閒聊 | AIClient（最低約束） |

純 AI 無法保證關鍵字句被說（例「林榮華」必須在通關之夜由特定 NPC 說），所以必須有 authored 部分。純劇本失去 AI 動態與重玩價值。

---

## 2. 系統組件

```
DialogueUI ── 加 ChoiceButtonsContainer 支援 beat mode
   │  Mode A (AI):   InputRow + typewriter + AI streaming
   │  Mode B (Beat): ChoiceButtons + typewriter + 預寫文字
   │
   ├──► AIClient ──► TrustGate ──► NPCProfile (extends NPCConfig)
   │
   └──► BeatRunner (NEW autoload) ──► StoryBeat.tres

共用狀態：StoryManager.{player_flags, npc_relationships, completed_events}
                       + EventBus
```

互動入口流程：

```gdscript
func on_player_interact(npc_id: String) -> void:
    var beat: StoryBeat = BeatRegistry.find_active_beat(npc_id)
    if beat:
        BeatRunner.run(beat)
        return
    var profile: NPCProfile = NPCRegistry.get(npc_id)
    var trust: int = StoryManager.npc_relationships.get(npc_id, 0)
    var overlay: String = ChapterManager.get_npc_overlay(npc_id)
    var prompt: String = TrustGate.build_system_prompt(profile, trust, StoryManager.player_flags, overlay)
    DialogueUI.open_ai_mode(profile)
    AIClient.query_with_prompt(prompt, ...)
```

---

## 3. NPCProfile.gd（extends NPCConfig）

```gdscript
class_name NPCProfile extends NPCConfig

@export var era: String = "any"            # "modern" / "1983" / "any"

# trust >= threshold 解鎖的主題
@export var trust_revelations: Array = []
# [{ "threshold": 0,  "topics": ["藥行日常"] },
#  { "threshold": 60, "topics": ["承認家裡有上鎖房間"] }, ...]

# 必須對應 flag 為 true 才能說的禁忌
@export var forbidden_until_flag: Dictionary = {}
# {"林榮華": "ending_finale_active", ...}

@export var known_facts: Array[String] = []
@export var personality_voice: String = ""   # 「台語混國語、短句」
```

---

## 4. TrustGate.gd（system prompt 組裝器）

> **設計原則**：TrustGate 是純函式 helper，**所有依賴透過參數注入**，不直接呼叫任何 autoload。caller（AIClient / BeatRunner）負責從 ChapterManager / StoryManager 取資料再傳入。這讓 TrustGate 可單獨測試、避免循環依賴。

```gdscript
class_name TrustGate

static func build_system_prompt(
    profile: NPCProfile,
    trust: int,
    flags: Dictionary,
    chapter_overlay: String = ""   # ← caller 從 ChapterManager 取後傳入
) -> String:
    var parts: Array[String] = [profile.system_prompt]

    if not chapter_overlay.is_empty():
        parts.append("[章節背景] " + chapter_overlay)

    if profile.personality_voice:
        parts.append("[語氣] " + profile.personality_voice)

    var allowed: Array = []
    for u in profile.trust_revelations:
        if trust >= u.threshold: allowed.append_array(u.topics)
    if not allowed.is_empty():
        parts.append("[你願意聊] " + ", ".join(allowed))

    var forbidden: Array = []
    for topic in profile.forbidden_until_flag:
        if not flags.get(profile.forbidden_until_flag[topic], false):
            forbidden.append(topic)
    if not forbidden.is_empty():
        parts.append("[絕對不能提] " + ", ".join(forbidden))

    if not profile.known_facts.is_empty():
        parts.append("[你知道的事]\n - " + "\n - ".join(profile.known_facts))

    parts.append("[對玩家信任度] %d/100" % trust)
    return "\n".join(parts)
```

---

## 5. StoryBeat.gd resource

```gdscript
class_name StoryBeat extends Resource

@export var beat_id: String                       # 建議 chXX_<short_name>

# 觸發條件（AND）
@export var trigger_flags: Dictionary = {}        # {"found_map": true}
@export var trigger_event: String = ""
@export var trigger_npc_id: String = ""
@export var trigger_zone: String = ""

# 內容
@export var dialogue_lines: Array = []
# [{ "speaker": "阿謙", "text": "..." }, { "speaker": "narrator", "text": "..." }]
@export var choices: Array = []
# [{ "text": "拿起地圖", "set_flags": {"found_map": true} }, ...]

# 完成後副作用
@export var on_complete_flags: Dictionary = {}
@export var on_complete_event: String = ""
@export var blocks_input: bool = true             # cutscene mode
```

---

## 6. BeatRunner.gd（ChapterManager 內部子節點，非獨立 autoload）

> **架構決定**：BeatRunner 不獨立成 autoload，而是 ChapterManager `_ready` 時 `add_child(BeatRunner.new())`。對外 API 透過 ChapterManager 暴露：`ChapterManager.find_active_beat(npc_id)` / `ChapterManager.run_beat(beat, ui)`。理由：beat 屬章節範疇，應與章節同權責；避免 autoload 數量繼續膨脹。

職責：
1. `scan_dir(path)` 掃 `chapters/*/beats/*.tres`，由 ChapterManager 呼叫
2. `find_active_beat(npc_id)` 給 BaseNPC 互動時查詢（依 trigger 條件）
3. `run(beat, ui)` 跑 beat → 透過 DialogueUI signals 推進
4. 顯示 choices → set flags、record `beat_done_<id>` event 防重觸發
5. emit `on_complete_event` / set `on_complete_flags`
6. 關 DialogueUI、解 input lock。ESC 中止 → 視為取消（不寫 flags）

---

## 7. DialogueUI 擴充

```
DialogueUI
└── Panel/VBoxOuter
    ├── HBox (Portrait + Text)
    ├── InputRow (LineEdit + SendButton)         ← AI mode
    └── ChoiceButtonsContainer (NEW, VBox)        ← Beat mode
```

新 API：`open_ai_mode(profile)` / `open_beat_mode(beat)` / `show_choices(choices) -> Signal` / `switch_to_ai_mode(profile)`（beat 結束直接接 AI，無斷點）。

---

## 8. EraManager.gd（時空切換）

```gdscript
extends Node
signal era_changed(from: String, to: String)

var current_era: String = "modern"
var era_state: Dictionary = {
    "modern": { "time_hours": 9.0, "save_position": Vector2.ZERO },
    "1983":   { "time_hours": 6.0, "save_position": Vector2.ZERO },
}

func travel_to(target_era: String, spawn_zone: String) -> void:
    # 1. 存當前 era 位置/時間
    # 2. 切到 zone_xxx_<target_era>
    # 3. 還原目標 era 狀態
    # 4. emit era_changed
```

NPC 由 `era` 過濾顯示（林榮昌 1983 only / 老周 modern only）。

---

## 9. 與既有系統整合

| 既有 | 整合方式 |
|---|---|
| `ChapterConfig.npc_overlays` | TrustGate 第二步讀取 |
| `StoryManager.npc_relationships` | trust 來源（-100~100）|
| `StoryManager.player_flags` | flags 來源 |
| `EventBus` | BeatRunner 監聽 |
| `events.gd` (per chapter) | 維持原邏輯，加 set_flag / emit_event 觸發 beats |
| `AIClient.query()` | system prompt 改由 TrustGate 接管 |
| `DialogueUI.tscn` | 加 `ChoiceButtonsContainer`，mode 切換 |

---

## 10. 檔案結構

```
game/src/
├── core/classes/  +NPCProfile.gd  +StoryBeat.gd  +TrustGate.gd
├── autoload/      +BeatRunner.gd  +EraManager.gd  (AIClient/ChapterManager 改)
├── ui/dialogue/   DialogueUI.gd/.tscn 擴充
└── chapters/chapter_NN_xxx/
        ├── chapter.tres
        ├── events.gd
        ├── beats/      ← NEW (.tres beats)
        ├── npcs/       ← NEW (章節 NPCProfile.tres)
        └── ...
```

基底 `entities/npcs/definitions/<id>.tres` 不分章節保留。

---

## 11. 實作 Phase

**Phase 1（最小可行，2-3 天 / 28-30h）**
- NPCProfile / TrustGate / StoryBeat / BeatRunner（基本 state machine）
- DialogueUI ChoiceButtonsContainer + mode 切換
- AIClient prompt builder 改用 TrustGate
- 寫 `chapter_01_arrival/beats/ch1_opening_iron_door.tres` 跑通
- 1 個 NPCProfile（林榮昌）測試 trust gate

**Phase 2（Chapter 1 完整，1-2 週）**
- EraManager autoload + zone modern/1983 雙版本
- 11 beats / 5 NPCProfile（林榮昌、阿嬤、陳秀琴、林小威、阿桃姨）
- 信任值累積邏輯（送藥 quest、辨藥小遊戲）
- 通關之夜長 beat（鎖死「林榮華」）

**Phase 3（評估）** — 一章 >30 beats 且 Inspector 變慢 → 評估導入 Dialogue Manager DSL。

---

## 12. 設計準則

- **Authored 永遠優先**：active beat 存在時 AI 不啟動
- **NPCProfile 不可空白**：所有有名 NPC 都要有 profile
- **forbidden_until_flag 是硬規則**：兩層防線 — prompt 約束 + post-processing 在 `AIClient.response_complete` 過濾未解鎖詞替換為「他/那個人」並 log
- **Era 過濾**：時空錯亂 NPC 由 `BaseNPC` 自動隱藏
- **Beat 完成必設 flag**：避免重觸發
- **保留 `ChapterConfig.npc_overlays`**：作為 TrustGate 一部分而非取代

---

## 13. Save / Load

- `BeatRunner` 已完成 beat ID → `StoryManager.completed_events`
- 已完成 beats 不重觸發
- AI 對話 history → `StoryManager.conversation_histories`

---

## 14. 相關文件

- [DialogueUI.gd](../game/src/ui/dialogue/DialogueUI.gd) / [AIClient.gd](../game/src/autoload/AIClient.gd)
- [chapter-development.md](chapter-development.md) / [addons.md](addons.md)
- 第一章劇本：[temp/Chapter 1：鐵門後的那個人.txt](../temp/Chapter%201%EF%BC%9A%E9%90%B5%E9%96%80%E5%BE%8C%E7%9A%84%E9%82%A3%E5%80%8B%E4%BA%BA.txt)
