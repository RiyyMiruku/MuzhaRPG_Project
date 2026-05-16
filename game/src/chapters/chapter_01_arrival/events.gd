## Chapter 01 Arrival — 章節事件
##
## 監聽:
##   - 進入 zone_pharmacy(現代,還沒觸發過開鐵門 cutscene) → 跑 open_iron_door
##   - 進入 zone_pharmacy(1983,還沒見過林榮昌) → meet_lin_rongchang beat 自己會接(by trigger_flags)
##   - emit_event "ch1_first_travel_done" → 視覺提示已穿越
##   - 通關條件:beat "ch1_finale_say_name" 完成 → 標記章節完成
extends RefCounted

const OPEN_IRON_DOOR_CUTSCENE: String = (
	"res://src/chapters/chapter_01_arrival/cutscenes/ch1_open_iron_door.tres"
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
	# 第一次走進藥行(現代):跑開鐵門 cutscene → 穿越到 1983
	if (
		zone_id == "zone_pharmacy"
		and EraManager.current_era == "modern"
		and not StoryManager.completed_events.has("ch1_first_travel_done")
	):
		EventBus.cutscene_requested.emit(OPEN_IRON_DOOR_CUTSCENE)


# ── Event-driven completion ─────────────────────────────────────────────────
func _on_event_recorded(event_id: String) -> void:
	# Chapter 通關條件:beat "ch1_finale_say_name" 完成
	if event_id == "ch1_finale_said_brother_name":
		StoryManager.player_flags["chapter_completed_ch01_arrival"] = true
		ChapterManager.complete_current()
