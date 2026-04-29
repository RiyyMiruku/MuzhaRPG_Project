# Project Muzha — Architecture Blueprint

> 文檔導覽：[INDEX](INDEX.md) — **對象**：程式 / 系統設計人。**用途**：技術架構參考。
> Last updated: 2026-04-28

## System Architecture

```
Godot 4.6 (Frontend)
├─ Autoloads: GameManager, StoryManager, ChapterManager, BeatRunner,
│             EraManager, AIClient, QuestManager, UIManager, EventBus
├─ Scene tree: MainWorld → ZoneContainer → [Active Zone]
│              UILayer (HUD, DialogueUI, QuestJournal, PauseMenu, ...)
└─ Sidecar: llama-server @ 127.0.0.1:8000  (Qwen-3.5-0.8B Q4_K_M)
```

## Directory Structure (high level)

```
MuzhaRPG_Project/
├── ai_engine/         # llama-server config + models (gitignored)
├── art_source/        # Build-time character source (序列圖 + metadata.json)
├── scripts/           # generate_spritesheet.py / import_assets.py / test_ping.py
└── game/              # Godot 4 project
    ├── assets/        # fonts, spritesheet_cache/, textures/{portraits,environment}/
    └── src/
        ├── autoload/  # 9 個 singleton（見下表）
        ├── core/      # classes/ (resources + helpers) + components/
        ├── entities/  # player/ + npcs/{BaseNPC, definitions/}
        ├── chapters/  # chapter_template/ + chapter_NN_xxx/{beats, npcs, events.gd}
        ├── maps/      # main_world.tscn + zones/ + tilesets/ + props/{nature,urban}
        ├── quests/    # *.tres
        └── ui/        # dialogue/, menus/, ScreenTransition
```

完整詳細結構詳見實際資料夾或 `git ls-tree`。

## Autoload Responsibilities

| Autoload | Responsibility |
|----------|----------------|
| **GameManager** | 狀態機、save/load、server process lifecycle |
| **StoryManager** | Zone 追蹤、event history、NPC relationships、game time、AI context |
| **ChapterManager** | Chapter 載入/切換、NPC overlay、events 註冊 |
| **BeatRunner** *(NEW)* | Authored StoryBeat 派發：掃 beats/、聽 flags/events、跑 dialogue + choices |
| **EraManager** *(NEW)* | 時代切換 (modern ↔ 1983)、per-era zone routing |
| **AIClient** | HTTP → llama-server，prompt 由 TrustGate 組裝 |
| **QuestManager** | Quest lifecycle |
| **UIManager** | UI panel stack（LIFO，input isolation，auto-pause）|
| **EventBus** | 純 signal bus |

核心 class（在 `core/classes/`）：BaseCharacter, NPCConfig, **NPCProfile** *(NEW)*, ChapterConfig, **StoryBeat** *(NEW)*, **TrustGate** *(NEW static)*, SpriteSheetLoader, QuestData, ZoneManager, PlaceholderSprite。

## Dialogue Pipeline

完整設計見 [dialogue-architecture.md](dialogue-architecture.md)。

```
Player presses E on NPC
   │
   ├─ BeatRunner.find_active_beat() 找到 beat?
   │     └─ Yes → DialogueUI.open_beat_mode()  → 預寫 lines + choices → set flags / emit event
   │
   └─ No → AI Mode:
          NPCProfile + trust + flags
            → TrustGate.build_system_prompt(...)
            → AIClient.query() → llama-server
            → DialogueUI typewriter
            → Post-filter forbidden words
```

`TrustGate.build_system_prompt()` 拼接：
1. `NPCProfile.system_prompt`（基底人格）
2. `ChapterManager.get_npc_overlay(npc_id)`（章節 delta）
3. `personality_voice` / `allowed_topics`（trust 解鎖） / `forbidden_topics`（flag 鎖死） / `known_facts` / `trust_value`

接著 `AIClient` 加上 conversation history（capped to memory_turns）+ assistant prefill `<think>\n</think>\n`，POST `/v1/chat/completions`。回應 strip `<think>` tag，過濾 forbidden 詞，emit `response_complete`。

## UI Stack

LIFO 堆疊：只有 top panel 可見且接收 input；非空時 game pause。
LiveMinimap 例外：HUD mode 常駐，expanded mode 才走 UIManager。

## Zone Map

```
Zhinan Temple (zone_zhinan)  [Master Guang]
       ↕
NCCU (zone_nccu) ←→ Muzha Market (zone_market) [Chen Ayi, Wang Bobo]
       ↕                                        
Daonan Riverside (zone_riverside) [Old Fisherman]
```

## Asset Import Pipeline

```
[Artist] temp/<bulk PNG>/ → AI 跑 import_assets.py --init → temp/import.toml
                          → AI 跑 import_assets.py        → props/<cat>/*.png + .tscn
[Artist in Godot] TileMapDual 塗地形 + 拖 prop .tscn 進 YSortRoot
```

入口：[scene-design-workflow.md](scene-design-workflow.md)。Manifest 細節：[scripts/import-assets-guide.md](../scripts/import-assets-guide.md)。地形：[tilemapdual-guide.md](tilemapdual-guide.md)。

兩腳本都 idempotent + `--dry-run`，未列出的資料夾會 WARNING（不靜默忽略）。

## Save System

- 存檔：`user://saves/save_N.json`（player pos / zone / StoryManager / QuestManager / play time）
- Keybinds：`user://keybinds.json`（獨立，啟動時載入）
- BeatRunner 已完成 beat ID 存進 `StoryManager.completed_events`，恢復不重觸發

## Chapter System

```
ChapterManager (autoload)
  _scan_chapters() on _ready  → load chapters/<id>/chapter.tres
  start_chapter(id)            → events_script.register(), emit signal
  complete_current()           → unregister, advance by order
  get_npc_overlay(npc_id)      → AIClient/TrustGate 用
```

`ChapterConfig` 欄位：chapter_id, display_name, order, prerequisites, zones_used, npcs_present, npc_overlays, events_script, quests, completion_flags。

完整作者 workflow：[chapter-development.md](chapter-development.md)。

## Development Progress

**Completed**：Phase 0-3（Godot boots, AI vertical slice, 4 zones + 4 NPCs, quests/save/time/pause, MainMenu/HUD/LiveMinimap/QuestJournal/KeybindSettings, UIManager stack, spritesheet pipeline, chapter skeleton）。

**Next**：
- Phase 4：pixel art / TileMap zones / 環境音 / CJK 字體
- Phase 5：build/export script、CPU-only fallback、跨平台測試、首次啟動 auto-setup（OS/GPU 偵測、模型下載 ~531MB from HF、engine from llama.cpp Releases）
- Stretch：streaming HTTP、NPC schedule、AI 生支線

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 英文 system prompt | 0.8B 模型英文 instruction token 較少，回中文不影響 |
| `--chat-template chatml` + assistant prefill `<think></think>` | 抑制 Qwen thinking mode 浪費 token |
| `127.0.0.1` 不用 `localhost` | Godot HTTP client on Windows 解析 localhost 失敗 |
| 非 streaming HTTP | Godot 4 HTTPRequest 不支援真 streaming，改用 thinking 動畫 |
| UIManager stack | 確保只有一個 panel 可見 + auto-pause |
| `ai_engine/config.json` | 與程式碼解耦，方便 llama.cpp 升級 |
