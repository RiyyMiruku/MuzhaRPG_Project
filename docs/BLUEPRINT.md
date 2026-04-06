# Project Muzha — Architecture Blueprint

> Last updated: 2026-04-06

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Godot 4.x (Frontend)                 │
│                                                         │
│  Autoloads (Global Singletons)                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ GameManager  │ │ StoryManager │ │  AIClient    │     │
│  │ state machine│ │ zone/events  │ │ HTTP + parse │     │
│  │ save/load    │ │ time system  │ │ context build│     │
│  └─────────────┘ └──────────────┘ └──────┬───────┘     │
│  ┌─────────────┐ ┌──────────────┐        │             │
│  │ QuestManager│ │  UIManager   │        │ HTTP POST   │
│  │ quest track │ │  UI stack    │        │ /v1/chat/    │
│  └─────────────┘ └──────────────┘        │ completions │
│  ┌─────────────┐                         │             │
│  │  EventBus   │                         │             │
│  │ decoupled   │                         │             │
│  │ signals     │                         │             │
│  └─────────────┘                         │             │
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
│   ├── scripts/
│   │   └── test_ping.py               # Python health check + chat test
│   └── models/
│       └── llama-b8583-bin-win-cuda-13.1-x64/
│           ├── llama-server.exe        # Inference server binary
│           └── Qwen3.5-0.8B-Q4_K_M.gguf  # Quantized LLM (531MB)
│
├── game/                              # Godot 4 project root
│   ├── project.godot                  # Engine config + input map
│   ├── assets/
│   │   └── fonts/                     # CJK fonts (Noto Sans TC)
│   │
│   └── src/
│       ├── autoload/                  # Global singletons
│       │   ├── GameManager.gd         # State machine, save/load, server lifecycle
│       │   ├── StoryManager.gd        # Zone/event tracking, time system, AI context
│       │   ├── AIClient.gd            # HTTP client to llama-server
│       │   ├── QuestManager.gd        # Quest tracking, auto-completion
│       │   ├── UIManager.gd           # UI stack (panel coordination)
│       │   └── EventBus.gd            # Decoupled signal bus
│       │
│       ├── core/
│       │   ├── classes/
│       │   │   ├── BaseCharacter.gd   # Shared movement + animation
│       │   │   ├── NPCConfig.gd       # NPC persona resource class
│       │   │   ├── QuestData.gd       # Quest definition resource class
│       │   │   ├── ZoneManager.gd     # Async zone loading + transitions
│       │   │   └── PlaceholderSprite.gd  # Runtime placeholder sprite generator
│       │   └── components/
│       │       └── ZoneTransitionArea.gd/.tscn  # Zone boundary trigger
│       │
│       ├── entities/
│       │   ├── player/
│       │   │   └── Player.gd/.tscn    # WASD movement, interaction
│       │   └── npcs/
│       │       ├── BaseNPC.gd/.tscn   # NPC base class, dialogue trigger
│       │       └── resources/         # NPC persona .tres files
│       │           ├── chen_ayi.tres      # Market vendor
│       │           ├── wang_bobo.tres     # Noodle shop owner
│       │           ├── master_guang.tres  # Temple keeper
│       │           └── old_fisher.tres    # Riverside fisherman
│       │
│       ├── maps/
│       │   ├── main_world.tscn        # Root scene (ZoneContainer + UI)
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
| **AIClient** | HTTP communication with llama-server, payload construction, response parsing | `query()`, `check_server_health()` |
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
    → System prompt (English instructions) + Context (key=value) + History + User message
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

```
System prompt (English, ~200 chars):
  "You are [name], [role] at [location]. Reply in Traditional Chinese only.
   [personality]. Keep reply under 50 chars. [examples]"

Runtime context injection (English, key=value):
  "[Context] time=下午2點, zone=政大正門, rel=stranger"

Conversation history (Chinese, capped to 6 turns):
  user: "你好" → assistant: "欸，你來啦！"

Assistant prefill (suppress thinking):
  "<think>\n</think>\n"
```

## Development Progress

### Completed
- [x] Phase 0: Godot project boots without errors
- [x] Phase 1: AI dialogue vertical slice (player ↔ NPC ↔ llama-server)
- [x] Phase 2: Zone system (4 zones, transitions, screen fade, 4 NPCs)
- [x] Phase 3: Quest system, save/load, game time, pause menu
- [x] UI: MainMenu, HUD, LiveMinimap (3-layer), QuestJournal, KeybindSettings
- [x] UIManager stack for panel coordination + input isolation

### Next Steps
- [ ] Phase 4: Pixel art sprites (replace placeholder rectangles)
- [ ] Phase 4: TileMap zones (replace ColorRect backgrounds)
- [ ] Phase 4: Ambient audio per zone
- [ ] Phase 4: CJK font global theme
- [ ] Phase 5: Build/export script (Godot + llama.cpp + model → single package)
- [ ] Phase 5: CPU-only fallback binary
- [ ] Phase 5: Cross-platform testing
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
