## ZoneManager — 區域切換管理器
## 負責非同步載入/卸載區域場景，管理玩家在區域間的移動。
## 掛載於 MainWorld 場景中，不是 Autoload。
class_name ZoneManager
extends Node

# ── Signals ─────────────────────────────────────────────────────────────────
signal zone_transition_started(from_zone: String, to_zone: String)
signal zone_transition_finished(zone_id: String)

# ── Config ──────────────────────────────────────────────────────────────────
## Zone 資料源：見 game/src/core/classes/Zones.gd（scene path / entry points / 連接）

# ── State ───────────────────────────────────────────────────────────────────
var current_zone_id: String = ""
var _current_zone_node: Node = null
var _zone_container: Node = null
var _player: Player = null
var _is_transitioning: bool = false

# ── References ──────────────────────────────────────────────────────────────
@export var screen_transition: ScreenTransition

func _ready() -> void:
	# 找到 ZoneContainer
	_zone_container = get_parent().find_child("ZoneContainer", false, false)
	if _zone_container == null:
		push_error("ZoneManager: ZoneContainer not found")
		return

	# 找到 ScreenTransition
	var st_node: Node = get_parent().find_child("ScreenTransition", true, false)
	if st_node is ScreenTransition:
		screen_transition = st_node as ScreenTransition

	# 連接 EventBus
	EventBus.zone_transition_requested.connect(_on_zone_transition_requested)

	# 偵測初始區域
	if _zone_container.get_child_count() > 0:
		_current_zone_node = _zone_container.get_child(0)
		current_zone_id = _get_zone_id_from_node(_current_zone_node)
		_player = _find_player()
		StoryManager.current_zone = current_zone_id

func _on_zone_transition_requested(zone_id: String, entry_point: String) -> void:
	transition_to_zone(zone_id, entry_point)

# ── Core Transition ─────────────────────────────────────────────────────────
func transition_to_zone(zone_id: String, entry_point: String = "default") -> void:
	if _is_transitioning:
		return
	if zone_id == current_zone_id:
		return
	if not Zones.has_zone(zone_id):
		push_error("ZoneManager: Unknown zone: " + zone_id)
		return

	_is_transitioning = true
	var old_zone: String = current_zone_id
	zone_transition_started.emit(old_zone, zone_id)
	GameManager.change_state(GameManager.GameState.LOADING)

	# 1. 淡出
	if screen_transition:
		screen_transition.fade_out()
		await screen_transition.fade_finished

	# 2. 卸載舊區域
	if _current_zone_node:
		_zone_container.remove_child(_current_zone_node)
		_current_zone_node.queue_free()
		_current_zone_node = null

	# 3. 非同步載入新區域
	var scene_path: String = Zones.scene_path(zone_id)
	ResourceLoader.load_threaded_request(scene_path)

	# 等待載入完成
	while ResourceLoader.load_threaded_get_status(scene_path) != ResourceLoader.THREAD_LOAD_LOADED:
		await get_tree().process_frame

	var packed_scene: PackedScene = ResourceLoader.load_threaded_get(scene_path) as PackedScene
	if packed_scene == null:
		push_error("ZoneManager: Failed to load zone: " + scene_path)
		# 還原畫面避免永久黑屏
		if screen_transition:
			screen_transition.fade_in()
			await screen_transition.fade_finished
		GameManager.change_state(GameManager.GameState.EXPLORING)
		_is_transitioning = false
		EventBus.hud_message_requested.emit("區域載入失敗：%s" % zone_id, 3.0)
		return

	# 4. 實例化新區域
	_current_zone_node = packed_scene.instantiate()
	_zone_container.add_child(_current_zone_node)
	current_zone_id = zone_id
	StoryManager.current_zone = zone_id
	StoryManager.unlock_zone(zone_id)
	# 記錄「已造訪」事件，供任務系統判定
	StoryManager.record_event("visited_" + zone_id.replace("zone_", ""))

	# 5. 定位玩家到入口點
	_player = _find_player()
	if _player:
		_player.global_position = Zones.entry_position(zone_id, entry_point)

	# 6. 淡入
	if screen_transition:
		screen_transition.fade_in()
		await screen_transition.fade_finished

	_is_transitioning = false
	GameManager.change_state(GameManager.GameState.EXPLORING)
	zone_transition_finished.emit(zone_id)
	EventBus.zone_loaded.emit(zone_id)

# ── Helpers ──────────────────────────────────────────────────────────────────
func _find_player() -> Player:
	var players: Array[Node] = get_tree().get_nodes_in_group("player")
	if not players.is_empty():
		return players[0] as Player
	# Fallback: 搜尋場景樹
	var result: Node = _zone_container.find_child("Player", true, false)
	if result is Player:
		return result as Player
	return null

func _get_zone_id_from_node(node: Node) -> String:
	var node_name: String = node.name.to_lower()
	for zone_id: String in Zones.all_ids():
		if node_name.contains(zone_id.replace("zone_", "")):
			return zone_id
	return ""
