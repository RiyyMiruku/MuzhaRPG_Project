## Chapter 01 Arrival — 章節事件
##
## 觸發鏈：
##   zone_pharmacy(現代,首次) → ch1_open_iron_door cutscene → 穿越到 1983
##   zone_pharmacy_backyard(1983) + clue_locked_room → ch1_ama_incense cutscene
##   got_locked_room_key + 進入 backyard → ch1_enter_locked_room cutscene
##   ch1_finale_said_brother_name → ch1_finale_reveal cutscene → 章節完成
extends RefCounted

const OPEN_IRON_DOOR_CUTSCENE: String = (
	"res://src/chapters/chapter_01_arrival/cutscenes/ch1_open_iron_door.tres"
)
const AMA_INCENSE_CUTSCENE: String = (
	"res://src/chapters/chapter_01_arrival/cutscenes/ch1_ama_incense.tres"
)
const ENTER_LOCKED_ROOM_CUTSCENE: String = (
	"res://src/chapters/chapter_01_arrival/cutscenes/ch1_enter_locked_room.tres"
)
const FINALE_REVEAL_CUTSCENE: String = (
	"res://src/chapters/chapter_01_arrival/cutscenes/ch1_finale_reveal.tres"
)

func register(_manager: Node) -> void:
	EventBus.zone_loaded.connect(_on_zone_loaded)
	StoryManager.event_recorded.connect(_on_event_recorded)

func unregister(_manager: Node) -> void:
	if EventBus.zone_loaded.is_connected(_on_zone_loaded):
		EventBus.zone_loaded.disconnect(_on_zone_loaded)
	if StoryManager.event_recorded.is_connected(_on_event_recorded):
		StoryManager.event_recorded.disconnect(_on_event_recorded)


# ── Zone entry triggers ─────────────────────────────────────────────────────
func _on_zone_loaded(zone_id: String) -> void:
	# 第一次走進藥行(現代)：跑開鐵門 cutscene → 穿越到 1983
	if (
		zone_id == "zone_pharmacy"
		and EraManager.current_era == "modern"
		and not StoryManager.completed_events.has("ch1_first_travel_done")
	):
		EventBus.cutscene_requested.emit(OPEN_IRON_DOOR_CUTSCENE)

	# 進入後院(1983)：看到阿嬤燒香（需已知道上鎖房間線索）
	if (
		zone_id == "zone_pharmacy_backyard"
		and EraManager.current_era == "1983"
		and StoryManager.player_flags.get("clue_locked_room", false)
		and not StoryManager.player_flags.get("saw_ama_incense", false)
	):
		EventBus.cutscene_requested.emit(AMA_INCENSE_CUTSCENE)

	# 拿到鑰匙後再次進入後院：開鎖進房間
	if (
		zone_id == "zone_pharmacy_backyard"
		and EraManager.current_era == "1983"
		and StoryManager.player_flags.get("got_locked_room_key", false)
		and not StoryManager.player_flags.get("found_ronghua_relic", false)
	):
		EventBus.cutscene_requested.emit(ENTER_LOCKED_ROOM_CUTSCENE)


# ── Event-driven completion ─────────────────────────────────────────────────
func _on_event_recorded(event_id: String) -> void:
	# 通關對話完成 → 跑結局 cutscene
	if event_id == "ch1_finale_said_brother_name":
		EventBus.cutscene_requested.emit(FINALE_REVEAL_CUTSCENE)

	# 結局 cutscene 結束 → 標記章節完成
	if event_id == "ch1_chapter_complete":
		StoryManager.player_flags["chapter_completed_ch01_arrival"] = true
		ChapterManager.complete_current()
