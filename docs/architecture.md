# Project Muzha — Architecture Blueprint

> Last updated: 2026-04-27

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Godot 4.x (Frontend)                 │
│                                                         │
│  Autoloads (Global Singletons)                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ GameManager  │ │ StoryManager │ │  AIClient    │     │
│  │ state machine│ │ zone/events  │ │ HTTP + parse │     │
│  │ save/load    │ │ time system  │ │ + chapter    │     │
│  └─────────────┘ └──────────────┘ │ overlay inject│     │
│  ┌─────────────┐ ┌──────────────┐ └──────┬───────┘     │
│  │ QuestManager│ │ChapterManager│        │             │
│  │ quest track │ │ chapter +    │        │ HTTP POST   │
│  │             │ │ NPC overlays │        │ /v1/chat/    │
│  └─────────────┘ └──────────────┘        │ completions │
│  ┌─────────────┐ ┌──────────────┐        │             │
│  │  UIManager  │ │  EventBus    │        │             │
│  │  UI stack   │ │  decoupled   │        │             │
│  │             │ │  signals     │        │             │
│  └─────────────┘ └──────────────┘        │             │
│                                          ▼             │
│  Scene Tree                    ┌─────────────────┐     │
│  ┌─ MainWorld                  │  llama-server   │     │
│  │  ├─ ZoneContainer           │  (Sidecar)      │     │
│  │  │  └─ [Active Zone]        │  localhost:8000  │     │
│  │  │     ├─ Player            │                  │     │
│  │  │     ├─ NPCs              │  Model:          │     │
│  │  │     └─ TransitionAreas   │  Qwen-3.5-0.8B  │     │
│  │  ├─ ZoneManager             │  Q4_K_M (GGUF)  │     │
│  │  ├─ UILayer                 └─────────────────┘     │
│  │  │  ├─ HUD + LiveMinimap                            │
│  │  │  ├─ DialogueUI                                   │
│  │  │  ├─ QuestJournal                                 │
│  │  │  ├─ PauseMenu                                    │
│  │  │  ├─ KeybindSettings                              │
│  │  │  └─ MainMenu                                     │
│  │  └─ ScreenTransition                                │
│  └────────────────────────────────────────────────────  │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure (Current)

```
MuzhaRPG_Project/
├── ai_engine/
│   ├── config.json                    # Server config (port, paths, GPU layers)
│   ├── start_server.ps1               # One-click server launcher
│   └── models/                        # GGUF models (gitignored)
│
├── art_source/                        # Build-time character source (not Godot-imported)
│   └── characters/
│       ├── 1-asset-creation.md        # Art prompt + spec
│       ├── 2-spritesheet-workflow.md  # Compile pipeline
│       ├── 3-asset-usage.md           # Runtime usage + 5-stage flow
│       └── <id>/                      # Per character: chen_ayi, master_guang, ...
│           ├── metadata.json
│           ├── rotations/
│           └── animations/{idle,walk}/
│
├── scripts/
│   ├── generate_spritesheet.py        # art_source/ → spritesheet_cache/ compiler
│   └── test_ping.py                   # llama-server health check
│
├── game/                              # Godot 4 project root
│   ├── project.godot                  # Engine config + input map + autoloads
│   ├── assets/
│   │   ├── fonts/                     # CJK fonts (Noto Sans TC)
│   │   ├── spritesheet_cache/         # Compiled per-character spritesheets (runtime)
│   │   │   ├── atlas_config.json      # Animation row/col mapping
│   │   │   └── <id>.png               # chen_ayi.png, master_guang.png, ...
│   │   └── textures/
│   │       ├── portraits/<id>.png     # Dialogue portraits (96×96)
│   │       └── environment/
│   │           ├── tilesets/<zone>/   # autotile + handpainted tilesets
│   │           └── props/{nature,urban}/  # Per-prop PNGs
│   │
│   └── src/
│       ├── autoload/                  # Global singletons
│       │   ├── GameManager.gd         # State machine, save/load, server lifecycle
│       │   ├── StoryManager.gd        # Zone/event tracking, time, AI context
│       │   ├── ChapterManager.gd      # Chapter switching + NPC overlay injection
│       │   ├── AIClient.gd            # HTTP client (auto-injects chapter overlay)
│       │   ├── QuestManager.gd        # Quest tracking, auto-completion
│       │   ├── UIManager.gd           # UI stack (panel coordination)
│       │   └── EventBus.gd            # Decoupled signal bus
│       │
│       ├── core/
│       │   ├── classes/
│       │   │   ├── BaseCharacter.gd   # Shared movement + animation
│       │   │   ├── NPCConfig.gd       # NPC persona resource (npc_id is master key)
│       │   │   ├── ChapterConfig.gd   # Chapter resource (overlays + flags + events)
│       │   │   ├── SpriteSheetLoader.gd  # Runtime spritesheet loader
│       │   │   ├── QuestData.gd       # Quest definition resource
│       │   │   ├── ZoneManager.gd     # Async zone loading + transitions
│       │   │   └── PlaceholderSprite.gd  # Runtime placeholder generator
│       │   └── components/
│       │       └── ZoneTransitionArea.gd/.tscn  # Zone boundary trigger
│       │
│       ├── entities/
│       │   ├── player/
│       │   │   └── Player.gd/.tscn    # WASD movement, interaction
│       │   └── npcs/
│       │       ├── BaseNPC.gd/.tscn   # NPC base, dialogue trigger
│       │       └── definitions/       # NPC base persona .tres
│       │           ├── chen_ayi.tres
│       │           ├── wang_bobo.tres
│       │           ├── master_guang.tres
│       │           └── old_fisher.tres
│       │
│       ├── chapters/                  # Chapter-scoped story content
│       │   ├── chapter_template/      # Copy this to create new chapters
│       │   │   ├── chapter.tres
│       │   │   ├── events.gd
│       │   │   └── README.md
│       │   └── chapter_01_arrival/    # Sample chapter
│       │       ├── chapter.tres
│       │       ├── events.gd
│       │       └── README.md
│       │
│       ├── maps/
│       │   ├── main_world.tscn        # Root scene (ZoneContainer + UI)
│       │   ├── README.md              # Map system overview
│       │   ├── tilesets/              # TileSet .tres resources
│       │   ├── props/                 # Prop scenes
│       │   │   ├── Prop.gd            # Base class (foot anchor, collision, interact)
│       │   │   ├── PropTemplate.tscn
│       │   │   ├── README.md
│       │   │   └── {nature,urban}/    # Per-prop .tscn (paired with PNG)
│       │   └── zones/
│       │       ├── zone_nccu.tscn     # NCCU campus (hub)
│       │       ├── zone_market.tscn   # Muzha Market (2 NPCs)
│       │       ├── zone_zhinan.tscn   # Zhinan Temple (1 NPC)
│       │       └── zone_riverside.tscn # Daonan Riverside (1 NPC)
│       │
│       ├── quests/
│       │   ├── quest_visit_market.tres
│       │   └── quest_temple_mystery.tres
│       │
│       └── ui/
│           ├── ScreenTransition.gd/.tscn   # Fade in/out overlay
│           ├── dialogue/
│           │   └── DialogueUI.gd/.tscn     # Chat UI + typewriter
│           └── menus/
│               ├── HUD.gd/.tscn            # Zone/time/quest display
│               ├── LiveMinimap.gd           # 3-layer map (HUD/zone/world)
│               ├── MainMenu.gd/.tscn       # Title screen
│               ├── PauseMenu.gd/.tscn      # Pause + save/load
│               ├── QuestJournal.gd/.tscn   # Quest list panel
│               └── KeybindSettings.gd/.tscn # Rebindable key config
```

## Autoload Responsibilities

| Autoload | Responsibility | Key Methods |
|----------|---------------|-------------|
| **GameManager** | Game state machine, save/load, server process lifecycle | `change_state()`, `save_game()`, `load_game()` |
| **StoryManager** | Zone tracking, event history, NPC relationships, game time, AI context building | `build_ai_context()`, `record_event()`, `serialize()` |
| **ChapterManager** | Chapter loading, switching, NPC overlay lookup, chapter-event registration | `start_chapter()`, `current()`, `get_npc_overlay()`, `complete_current()` |
| **AIClient** | HTTP comm with llama-server, payload construction (auto-injects chapter overlay), response parsing | `query()`, `check_server_health()` |
| **QuestManager** | Quest lifecycle (start/complete), prerequisite checking, reward distribution | `start_quest()`, `complete_quest()` |
| **UIManager** | UI panel stack management, input isolation, pause coordination | `push()`, `pop()`, `pop_all()`, `toggle()` |
| **EventBus** | Decoupled inter-system signals | Signals only, no methods |

## AI Pipeline

```
Player Input → BaseNPC._on_player_input()
    ↓
StoryManager.build_ai_context(npc_id)
    → { zone, time_of_day, relationship, recent_events, conversation_history }
    ↓
AIClient._build_chat_payload(npc_config, user_input, context)
    → System prompt = npc_config.system_prompt
        + ChapterManager.get_npc_overlay(npc_id)   ← Chapter-specific delta
        + Context string (zone, time, relationship, recent events)
    → + Conversation history (capped to memory_turns)
    → + User message
    → Append assistant prefill: "<think>\n</think>\n" (suppress thinking mode)
    ↓
HTTP POST → http://127.0.0.1:8000/v1/chat/completions
    ↓
AIClient._on_query_completed()
    → Strip <think> tags → Emit response_complete signal
    ↓
DialogueUI._on_ai_response_complete()
    → Typewriter animation display
```

## UI Stack System

```
UIManager maintains a LIFO stack of Control panels.
Only the TOP panel is visible and receives input.
When stack is non-empty, game is paused + input is intercepted.

Examples:
  [] → EXPLORING (normal gameplay)
  [MainMenu] → title screen, game paused
  [PauseMenu] → pause menu
  [PauseMenu, KeybindSettings] → settings on top of pause
  [QuestJournal] → quest list, game paused
  [MapExpanded] → expanded map view, game paused

LiveMinimap is special: HUD mode always visible, expanded mode uses UIManager.
```

## Zone Map

```
        Zhinan Temple (zone_zhinan)
        [Master Guang]
              ↕
NCCU (zone_nccu)  ←→  Muzha Market (zone_market)
     [hub, no NPC]      [Chen Ayi, Wang Bobo]
              ↕
        Daonan Riverside (zone_riverside)
        [Old Fisherman]
```

## Save System

- Path: `user://saves/save_N.json`
- Contents: player position, zone, StoryManager state, QuestManager state, play time
- Keybinds: `user://keybinds.json` (separate, always loaded on startup)

## NPC Prompt Structure

Three layers compose the system prompt at runtime:

```
[1. Base persona] — NPCConfig.system_prompt (English, ~200 chars; per-character, never changes)
  "You are [name], [role] at [location]. Reply in Traditional Chinese only.
   [personality]. Keep reply under 50 chars. [examples]"

[2. Chapter overlay] — ChapterManager.get_npc_overlay(npc_id) (per-chapter delta)
  "[章節背景] （玩家剛搬來木柵第一天，你不認識他...）"

[3. Runtime context] — StoryManager.build_ai_context(npc_id) (per-call dynamic)
  "[Context] time=下午2點, zone=政大正門, rel=stranger, recent_events=[...]"
```

Plus conversation history (Chinese, capped to memory_turns) and assistant prefill `<think>\n</think>\n`.

**Single source of truth per layer**:
- Base persona: `entities/npcs/definitions/<id>.tres` (one file per character)
- Chapter overlay: `chapters/<id>/chapter.tres` `npc_overlays` dict
- Runtime state: StoryManager (relationships, flags, events)

## Chapter System

```
ChapterManager (autoload)
  ├── _scan_chapters() on _ready()    → load all chapters/<id>/chapter.tres
  ├── current() → ChapterConfig       → for AIClient + UI queries
  ├── start_chapter(id)               → register events.gd, emit signals
  ├── complete_current()              → unregister, advance to next by order
  ├── get_npc_overlay(npc_id)         → AIClient calls per dialogue
  └── is_npc_active(npc_id)           → optional NPC visibility filter

ChapterConfig fields:
  chapter_id, display_name, order, prerequisites
  zones_used, npcs_present
  npc_overlays = { npc_id: "delta string" }
  events_script (RefCounted with register/unregister)
  quests, completion_flags

Lifecycle:
  start_chapter("ch01_arrival")
    → events_script.new().register(manager)
    → emit chapter_started
    → (gameplay)
    → events.gd watches for completion_flags
    → complete_current() → emit chapter_completed → start next
```

See [chapter-development.md](chapter-development.md) for the full author workflow.

## Development Progress

### Completed
- [x] Phase 0: Godot project boots without errors
- [x] Phase 1: AI dialogue vertical slice (player ↔ NPC ↔ llama-server)
- [x] Phase 2: Zone system (4 zones, transitions, screen fade, 4 NPCs)
- [x] Phase 3: Quest system, save/load, game time, pause menu
- [x] UI: MainMenu, HUD, LiveMinimap (3-layer), QuestJournal, KeybindSettings
- [x] UIManager stack for panel coordination + input isolation
- [x] Spritesheet pipeline (art_source/ → spritesheet_cache/, single-ID convention)
- [x] Chapter system skeleton (ChapterManager, ChapterConfig, AIClient overlay injection)

### Next Steps
- [ ] Phase 4: Pixel art sprites (replace placeholder rectangles)
- [ ] Phase 4: TileMap zones (replace ColorRect backgrounds)
- [ ] Phase 4: Ambient audio per zone
- [ ] Phase 4: CJK font global theme
- [ ] Phase 5: Build/export script (Godot + llama.cpp + model → single zip)
- [ ] Phase 5: CPU-only fallback binary
- [ ] Phase 5: Cross-platform testing (Windows CUDA/CPU, macOS ARM/Intel, Linux)
- [ ] Phase 5: Auto-setup system — first launch auto-detection & download
  - Detect OS via `OS.get_name()` → choose correct llama-server build
  - Detect GPU via `RenderingServer.get_video_adapter_vendor()` → CUDA / Metal / CPU-only
  - Auto-set `config.json` gpu_layers (NVIDIA/Apple Silicon → 99, others → 0)
  - If `models/*.gguf` missing → prompt user & download from Hugging Face (~531MB)
  - If `engines/llama-server` missing → download from llama.cpp GitHub Releases
  - Download progress UI with cancel/retry support
  - File hosting: GitHub Releases (engine) + Hugging Face (model)
- [ ] Stretch: Streaming HTTP responses (StreamPeerTCP)
- [ ] Stretch: NPC schedule system (different NPCs at different times)
- [ ] Stretch: Dynamic side quest generation via AI

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| English system prompts | 0.8B model consumes fewer tokens with English instructions, replies in Chinese |
| `--chat-template chatml` | Prevents Qwen from entering thinking mode (wastes all tokens on reasoning) |
| Assistant prefill `<think></think>` | Extra safety: tricks model into skipping think phase |
| `127.0.0.1` instead of `localhost` | Godot's HTTP client on Windows fails to resolve `localhost` |
| Non-streaming HTTP | Godot 4 HTTPRequest doesn't support true streaming; shows "thinking" animation instead |
| UIManager stack pattern | Ensures only one panel visible, auto-pause, no input leaking to game |
| PlaceholderSprite runtime generation | No art files needed for development; auto-skipped when real sprites are assigned |
| `ai_engine/config.json` | Decouples binary/model paths from code; survives llama.cpp version upgrades |
