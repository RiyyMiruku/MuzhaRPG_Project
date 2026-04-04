extends Node

# ── State ──────────────────────────────────────────────────────────────────
var unlocked_zones: Array[String] = ["zone_nccu"]
var completed_events: Array[String] = []
var player_flags: Dictionary = {}
var npc_relationships: Dictionary = {}          # npc_id -> int (-100 to 100)
var conversation_histories: Dictionary = {}     # npc_id -> Array[Dictionary]
var current_zone: String = "zone_nccu"
var game_time_hours: float = 14.0               # 0.0 - 24.0 (in-game clock)

# ── Zone Display Names ─────────────────────────────────────────────────────
const ZONE_DISPLAY: Dictionary = {
	"zone_nccu":      "政大正門",
	"zone_market":    "木柵市場",
	"zone_zhinan":    "指南宮",
	"zone_riverside": "道南河濱公園",
}

func _ready() -> void:
	pass

# ── Context Builder (核心方法) ────────────────────────────────────────────
func build_ai_context(npc_id: String) -> Dictionary:
	return {
		"zone": current_zone,
		"zone_display": ZONE_DISPLAY.get(current_zone, current_zone),
		"time_of_day": _get_time_string(),
		"time_period": _get_time_period(),
		"relationship": npc_relationships.get(npc_id, 0),
		"recent_events": _get_recent_events(5),
		"player_visited_zones": unlocked_zones.duplicate(),
		"conversation_history": conversation_histories.get(npc_id, []).duplicate(),
	}

# ── Time Helpers ───────────────────────────────────────────────────────────
func _get_time_string() -> String:
	var h: int = int(game_time_hours)
	var period: String = "上午" if h < 12 else "下午"
	var display_h: int = h if h <= 12 else h - 12
	if display_h == 0:
		display_h = 12
	return "%s%d點" % [period, display_h]

func _get_time_period() -> String:
	var h: int = int(game_time_hours)
	if h < 6:   return "deep_night"
	if h < 10:  return "morning"
	if h < 14:  return "noon"
	if h < 18:  return "afternoon"
	if h < 21:  return "evening"
	return "night"

func _get_recent_events(count: int) -> Array[String]:
	var total: int = completed_events.size()
	var start: int = max(0, total - count)
	var result: Array[String] = []
	for i in range(start, total):
		result.append(completed_events[i])
	return result

# ── Event Tracking ─────────────────────────────────────────────────────────
func record_event(event_id: String) -> void:
	if not completed_events.has(event_id):
		completed_events.append(event_id)

func set_flag(key: String, value: Variant) -> void:
	player_flags[key] = value

func get_flag(key: String, default: Variant = null) -> Variant:
	return player_flags.get(key, default)

func unlock_zone(zone_id: String) -> void:
	if not unlocked_zones.has(zone_id):
		unlocked_zones.append(zone_id)

func update_relationship(npc_id: String, delta: int) -> void:
	var current: int = npc_relationships.get(npc_id, 0)
	npc_relationships[npc_id] = clamp(current + delta, -100, 100)

func add_conversation_turn(npc_id: String, role: String, content: String) -> void:
	if not conversation_histories.has(npc_id):
		conversation_histories[npc_id] = []
	conversation_histories[npc_id].append({"role": role, "content": content})

# ── Persistence (Phase 3) ──────────────────────────────────────────────────
func serialize() -> Dictionary:
	return {
		"unlocked_zones": unlocked_zones,
		"completed_events": completed_events,
		"player_flags": player_flags,
		"npc_relationships": npc_relationships,
		"current_zone": current_zone,
		"game_time_hours": game_time_hours,
	}

func deserialize(data: Dictionary) -> void:
	unlocked_zones = data.get("unlocked_zones", ["zone_nccu"])
	completed_events = data.get("completed_events", [])
	player_flags = data.get("player_flags", {})
	npc_relationships = data.get("npc_relationships", {})
	current_zone = data.get("current_zone", "zone_nccu")
	game_time_hours = data.get("game_time_hours", 14.0)
	conversation_histories = {}  # Histories are session-only (not persisted)
