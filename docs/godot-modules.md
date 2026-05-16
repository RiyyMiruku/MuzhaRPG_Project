# Godot 實作模組清單

> 文檔導覽：[INDEX](INDEX.md) — **對象**：所有人。**用途**：Godot 端模組追蹤表，含檔案連結、功能、實作狀況。Python pipeline 不在此檔。
>
> **更新時機**：新增 autoload / class / scene component / UI panel 時。狀態欄變動時。
>
> **最後更新**：2026-05-15

---

## 圖例

| 狀態 | 意義 |
|---|---|
| ✅ 就緒 | 已實作並驗證,可被依賴 |
| ⚠️ 部分 | 框架在,但需要 chapter 內容 / wiring / 串接才會生效 |
| ❌ 未做 | 規劃中或待實作 |
| 🧪 測試 | 純測試用,不上 production |

---

## 1. Autoload(常駐 singleton)

`game/project.godot` `[autoload]` 段註冊。所有 autoload 隨遊戲啟動,跨場景常駐。

| Autoload | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `GameManager` | [GameManager.gd](../game/src/autoload/GameManager.gd) | State machine (MAIN_MENU/EXPLORING/DIALOGUE/PAUSED/LOADING) + save/load (JSON) + llama-server lifecycle (launch/poll health/shutdown) | ✅ |
| `EventBus` | [EventBus.gd](../game/src/autoload/EventBus.gd) | 全域 signal hub,20+ signals 用於解耦通訊(zone_transition / npc_interaction / dialogue / hud_message / ai_server) | ✅ |
| `StoryManager` | [StoryManager.gd](../game/src/autoload/StoryManager.gd) | 故事狀態 single source of truth:`player_flags` / `npc_relationships` (trust) / `current_zone` / `conversation_histories` / `completed_events` | ✅ |
| `ChapterManager` | [ChapterManager.gd](../game/src/autoload/ChapterManager.gd) | 載入當前 `chapter.tres`,套用 `npc_overlays`(章節限定 NPC system_prompt 差異),host BeatRunner 子節點 | ✅ |
| `QuestManager` | [QuestManager.gd](../game/src/autoload/QuestManager.gd) | 任務追蹤(接取/進度/完成判定),`QuestData.tres` 為單位 | ✅ |
| `AIClient` | [AIClient.gd](../game/src/autoload/AIClient.gd) | 對 llama-server HTTP 串流,管理 conversation history,需配合 TrustGate 組 system prompt | ✅ |
| `UIManager` | [UIManager.gd](../game/src/autoload/UIManager.gd) | UI 面板堆疊,只有最頂層接收輸入 | ✅ |

**規劃中的 autoload**:

| Autoload | 用途 | 狀態 |
|---|---|---|
| `TransitionManager` | 統一場景切換(fade-out → load → fade-in)入口 | ❌ 現由 `ZoneManager`(非 autoload)+ `ScreenTransition`(UI 元件)承擔,但兩者協作未完整 |
| `EraManager` | 1983 ↔ modern 時空切換,toggle Era group + CanvasModulate tint | ❌ |
| `CutsceneDirector` | 鏡頭 + 對白 + 等待 op sequence runner | ❌ |

---

## 2. Core Classes(資料 / 邏輯類別)

### 2.1 角色 / 移動

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `BaseCharacter` | [BaseCharacter.gd](../game/src/core/classes/BaseCharacter.gd) | 角色共用移動邏輯,Player + NPC 共同基底 | ✅ |
| `Player` | [Player.gd](../game/src/entities/player/Player.gd) / [Player.tscn](../game/src/entities/player/Player.tscn) | 玩家:WASD / 方向鍵 + E 互動 | ✅ |
| `BaseNPC` | [BaseNPC.gd](../game/src/entities/npcs/BaseNPC.gd) / [BaseNPC.tscn](../game/src/entities/npcs/BaseNPC.tscn) | NPC 基底,綁 NPCConfig,玩家靠近顯示提示,E 開對話 | ✅ |
| `SpriteSheetLoader` | [SpriteSheetLoader.gd](../game/src/core/classes/SpriteSheetLoader.gd) | 從 `<name>.{png,json}` spritesheet 動態建 SpriteFrames | ✅ |
| `PlaceholderSprite` | [PlaceholderSprite.gd](../game/src/core/classes/PlaceholderSprite.gd) | 程式化彩色方塊,SpriteFrames 缺失時 fallback | ✅ |

### 2.2 NPC 設定資源

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `NPCConfig` | [NPCConfig.gd](../game/src/core/classes/NPCConfig.gd) | 基底 NPC 設定 `.tres`:display_name / system_prompt / temperature 等 AI 參數 | ✅ |
| `NPCProfile` | [NPCProfile.gd](../game/src/core/classes/NPCProfile.gd) | extends NPCConfig,加 `era` / `trust_revelations` / `forbidden_until_flag` / `known_facts` / `personality_voice` | ⚠️ 類別在,**chapter 1 NPC .tres 內容未寫** |
| `TrustGate` | [TrustGate.gd](../game/src/core/classes/TrustGate.gd) | 純函式 helper:profile + trust + flags + overlay → 組裝完整 system prompt | ✅ |

### 2.3 對話 / 劇情

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `StoryBeat` | [StoryBeat.gd](../game/src/core/classes/StoryBeat.gd) | 預寫對白節拍 `.tres`:trigger 條件 + dialogue_lines + choices + on_complete_flags | ⚠️ 類別在,chapter 1 beat 內容只有 1 個 [test_chen_ayi_intro.tres](../game/src/chapters/chapter_01_arrival/beats/test_chen_ayi_intro.tres) |
| `BeatRunner` | [BeatRunner.gd](../game/src/core/classes/BeatRunner.gd) | 掃 chapters/*/beats/、依 trigger 找 active beat、跑 beat → 推 DialogueUI、set flags、防重觸發。ChapterManager 子節點 | ✅ |

### 2.4 章節資源

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `ChapterConfig` | [ChapterConfig.gd](../game/src/core/classes/ChapterConfig.gd) | `chapter.tres`:章節範圍 / 出場 NPC / npc_overlays(章節限定 NPC system_prompt 差異) | ✅ |
| chapter_01_arrival/events.gd | [events.gd](../game/src/chapters/chapter_01_arrival/events.gd) | 第一章 cross-cutting 流程邏輯(目前接近空殼) | ⚠️ 骨架在,流程未寫 |
| chapter_template/events.gd | [events.gd](../game/src/chapters/chapter_template/events.gd) | 新章節用 template | ✅ |

### 2.5 區域

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `Zones` | [Zones.gd](../game/src/core/classes/Zones.gd) | Zone 定義 single source of truth(display name / scene path / entry_points / world_pos / connects_to) | ⚠️ **只有 3 個舊 zone**(nccu/market/zhinan/riverside);chapter 1 新生的 7 個 zone **尚未註冊** |
| `ZoneManager` | [ZoneManager.gd](../game/src/core/classes/ZoneManager.gd) | 非 autoload,掛 main_world。聽 `zone_transition_requested` → load zone scene → place player at entry_point。配合 `ScreenTransition` 做 fade | ⚠️ 實作完整,但要新 zone 註冊到 `Zones.ALL` 才會被認得 |
| `ZoneTransitionArea` | [ZoneTransitionArea.gd](../game/src/core/components/ZoneTransitionArea.gd) / [.tscn](../game/src/core/components/ZoneTransitionArea.tscn) | Area2D 觸發器,玩家進入 emit `zone_transition_requested` | ✅ |

### 2.6 任務

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `QuestData` | [QuestData.gd](../game/src/core/classes/QuestData.gd) | 任務定義 `.tres`:id / title / objectives / rewards | ✅ |

---

## 3. UI

| Scene | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `DialogueUI` | [.gd](../game/src/ui/dialogue/DialogueUI.gd) / [.tscn](../game/src/ui/dialogue/DialogueUI.tscn) | NPC 對話介面:打字機動畫 + AI 等待提示 + 玩家輸入 + Beat mode(choice buttons) | ✅ AI mode + Beat mode 兩條路徑都實作(ChoiceButtonsContainer 在 `_ready` 程式生成) |
| `ScreenTransition` | [.gd](../game/src/ui/ScreenTransition.gd) / [.tscn](../game/src/ui/ScreenTransition.tscn) | 全畫面黑色 fade-in/out(ColorRect + Tween) | ✅ |
| `MainMenu` | [.gd](../game/src/ui/menus/MainMenu.gd) / [.tscn](../game/src/ui/menus/MainMenu.tscn) | 主選單(新遊戲 / 載入 / 設定 / 離開) | ✅ |
| `PauseMenu` | [.gd](../game/src/ui/menus/PauseMenu.gd) / [.tscn](../game/src/ui/menus/PauseMenu.tscn) | 暫停選單 | ✅ |
| `HUD` | [.gd](../game/src/ui/menus/HUD.gd) / [.tscn](../game/src/ui/menus/HUD.tscn) | 區域名 / 遊戲內時間 / 當前任務提示 | ✅ |
| `LiveMinimap` | [.gd](../game/src/ui/menus/LiveMinimap.gd) | 三層地圖(HUD 即時 / M 開大圖 / world map) | ✅ |
| `QuestJournal` | [.gd](../game/src/ui/menus/QuestJournal.gd) / [.tscn](../game/src/ui/menus/QuestJournal.tscn) | 任務日誌面板 | ✅ |
| `KeybindSettings` | [.gd](../game/src/ui/menus/KeybindSettings.gd) / [.tscn](../game/src/ui/menus/KeybindSettings.tscn) | 按鍵綁定 | ✅ |

---

## 4. 地圖 / 場景

### 4.1 主世界

| Scene | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| main_world | [main_world.tscn](../game/src/maps/main_world.tscn) | 遊戲主場景,host ZoneManager / ScreenTransition / UI overlay | ✅ |

### 4.2 Zone(目前的 7 個 chapter 1 zone + 舊 zone + 測試)

由 `scripts/build_zone.py` 從 YAML 產出。詳見 [docs/chapter-01-scene-automation-plan.md](chapter-01-scene-automation-plan.md)。

| Zone | 檔案 | 來源 YAML | 狀態 |
|---|---|---|---|
| zone_pharmacy_1983 | [.tscn](../game/src/maps/zones/zone_pharmacy_1983.tscn) | [pharmacy_1983.yaml](../story/chapters/chapter_01_arrival/zones/pharmacy_1983.yaml) | ⚠️ builder 產出,**未註冊到 Zones.ALL** |
| zone_pharmacy_modern | [.tscn](../game/src/maps/zones/zone_pharmacy_modern.tscn) | [pharmacy_modern.yaml](../story/chapters/chapter_01_arrival/zones/pharmacy_modern.yaml) | ⚠️ 同上 |
| zone_pharmacy_backyard | [.tscn](../game/src/maps/zones/zone_pharmacy_backyard.tscn) | [pharmacy_backyard.yaml](../story/chapters/chapter_01_arrival/zones/pharmacy_backyard.yaml) | ⚠️ 同上 |
| zone_market_1983 | [.tscn](../game/src/maps/zones/zone_market_1983.tscn) | [market_1983.yaml](../story/chapters/chapter_01_arrival/zones/market_1983.yaml) | ⚠️ 同上 |
| zone_market_modern | [.tscn](../game/src/maps/zones/zone_market_modern.tscn) | [market_modern.yaml](../story/chapters/chapter_01_arrival/zones/market_modern.yaml) | ⚠️ 同上 |
| zone_apartment_muzha | [.tscn](../game/src/maps/zones/zone_apartment_muzha.tscn) | [apartment_muzha.yaml](../story/chapters/chapter_01_arrival/zones/apartment_muzha.yaml) | ⚠️ 同上 |
| zone_law_office | [.tscn](../game/src/maps/zones/zone_law_office.tscn) | [law_office.yaml](../story/chapters/chapter_01_arrival/zones/law_office.yaml) | ⚠️ 同上 |
| zone_market | [.tscn](../game/src/maps/zones/zone_market.tscn) | (手寫,舊) | ✅ 在 Zones.ALL |
| zone_iso_test | [.tscn](../game/src/maps/zones/zone_iso_test.tscn) | (手寫) | 🧪 |
| zone_tilemapdual_test | [.tscn](../game/src/maps/zones/zone_tilemapdual_test.tscn) | (手寫,階段 0 驗證) | 🧪 |

### 4.3 Prop

| 類別 | 檔案 | 功能 | 狀態 |
|---|---|---|---|
| `Prop` (base) | [Prop.gd](../game/src/maps/props/Prop.gd) | 裝飾物共用基底(碰撞 + InteractArea) | ✅ |
| `PropTemplate.tscn` | [PropTemplate.tscn](../game/src/maps/props/PropTemplate.tscn) | 所有 prop instance 的母 scene | ✅ |
| 25+ 個 prop instance | [props/](../game/src/maps/props/) | chapter 1 用的所有 prop(藥櫃 / 燈籠 / 攤位 / 建築 ...) | ✅ Pipeline 已 import,全 25 個 .tscn 備齊 |

### 4.4 Addons

| Addon | 路徑 | 功能 | 狀態 |
|---|---|---|---|
| TileMapDual | [game/addons/TileMapDual/](../game/addons/TileMapDual/) | Dual-grid autotile,程式塗 cell 自動邊界拼接 | ✅ |
| PhantomCamera2D | (未安裝) | 鏡頭控制 / cutscene framing | ❌ |

---

## 5. 章節資源(chapter content)

| 章節 | 檔案 | 內容 | 狀態 |
|---|---|---|---|
| chapter_01_arrival | [chapter.tres](../game/src/chapters/chapter_01_arrival/chapter.tres) | 章節 metadata + npc_overlays | ⚠️ 骨架 |
| chapter 1 beats | [beats/](../game/src/chapters/chapter_01_arrival/beats/) | StoryBeat .tres × 1(目前只有 test) | ❌ 11 個正式 beat 待寫 |
| chapter 1 NPCProfile | (尚無 npcs/ 資料夾) | 7 個章節 NPC profile | ❌ |
| chapter 1 quests | (尚無 quests/) | 跑腿送藥、辨藥小遊戲、阿嬤信任值小事 | ❌ |
| chapter 1 cutscenes | (尚無 cutscenes/) | 開鐵門 / 第一次穿越 / 通關之夜 / 結尾身分證 | ❌ |
| chapter_template | [chapter_template/](../game/src/chapters/chapter_template/) | 新章節 template | ✅ |

---

## 6. 測試 scripts(非 production)

| Scene | 檔案 | 用途 | 狀態 |
|---|---|---|---|
| test_spritesheet_loader | [.gd](../game/src/test/test_spritesheet_loader.gd) / [.tscn](../game/src/test/test_spritesheet_loader.tscn) | 驗證 SpriteSheetLoader 從 spritesheet 正確建 SpriteFrames | 🧪 |
| zone_tilemapdual_test | [.tscn](../game/src/maps/zones/zone_tilemapdual_test.tscn) + [zone_baker_test.gd](../game/tools/zone_baker_test.gd) | TileMapDual @tool 程式塗驗證(階段 0) | 🧪 |
| zone_iso_test | [zone_iso_test.tscn](../game/src/maps/zones/zone_iso_test.tscn) | iso 投影 + autotile 視覺 sandbox | 🧪 |

---

## 7. 工具(Godot 端)

| 工具 | 檔案 | 用途 | 狀態 |
|---|---|---|---|
| `zone_baker` | [zone_baker.gd](../game/tools/zone_baker.gd) | `@tool` 腳本,builder 產的 zone .tscn 用,Inspector 按鈕一鍵 bake `terrain_cells` → TileMapDual | ✅ |
| `zone_baker_test` | [zone_baker_test.gd](../game/tools/zone_baker_test.gd) | 階段 0 驗證版本(5 格硬編碼) | 🧪 |

---

## 8. 主要缺口快覽(優先處理)

| 缺口 | 影響 | 工時估 |
|---|---|---|
| ❌ chapter 1 NPCProfile × 7 | NPC 互動會走純 AI fallback,沒 trust gate | 中等(每個 30 min) |
| ❌ chapter 1 StoryBeat × 11 | 主線錨點 missing,沒法通關 | 大(每個 1-2h,通關之夜 4h) |
| ❌ EraManager + 時空切換 mechanic | chapter 1 核心 mechanic 缺,不能穿越 | 中等(2-3h,看 zone hybrid 方案實作) |
| ❌ Cutscene + PhantomCamera2D | 重要 beat 缺電影感(開鐵門 / 第一次穿越) | 中等(3-4h) |

---

## 9. 相關文件

| 文檔 | 連結 |
|---|---|
| 對話系統設計 | [docs/dialogue-architecture.md](dialogue-architecture.md) |
| 章節 1 場景自動化 | [docs/chapter-01-scene-automation-plan.md](chapter-01-scene-automation-plan.md) |
| Tile autotile 設定 | [docs/tilemapdual-guide.md](tilemapdual-guide.md) |
| 場景設計工作流 | [docs/scene-design-workflow.md](scene-design-workflow.md) |
| 章節開發指南 | [docs/chapter-development.md](chapter-development.md) |
