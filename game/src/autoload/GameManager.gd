extends Node

# ── Signals ────────────────────────────────────────────────────────────────
signal game_state_changed(new_state: GameState)
signal server_ready()
signal server_failed(error: String)

# ── Enums ──────────────────────────────────────────────────────────────────
enum GameState { MAIN_MENU, EXPLORING, DIALOGUE, PAUSED, LOADING }

# ── State ──────────────────────────────────────────────────────────────────
var current_state: GameState = GameState.MAIN_MENU
var _server_pid: int = -1
var _ai_config: Dictionary = {}
var _time_played_sec: float = 0.0
var _pending_load_position: Vector2 = Vector2.INF  # INF = 無待載入位置

# ── Constants ──────────────────────────────────────────────────────────────
const CONFIG_PATH: String = "../../ai_engine/config.json"

# ── Lifecycle ──────────────────────────────────────────────────────────────
func _ready() -> void:
	_load_ai_config()

func _process(delta: float) -> void:
	if current_state == GameState.EXPLORING:
		_time_played_sec += delta
	# 載入存檔後定位玩家
	if _pending_load_position != Vector2.INF:
		var players: Array[Node] = get_tree().get_nodes_in_group("player")
		if not players.is_empty():
			players[0].global_position = _pending_load_position
			_pending_load_position = Vector2.INF

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		shutdown_server()

# ── Config ─────────────────────────────────────────────────────────────────
func _load_ai_config() -> void:
	var config_path: String = ProjectSettings.globalize_path("res://") + "../ai_engine/config.json"
	var file: FileAccess = FileAccess.open(config_path, FileAccess.READ)
	if file == null:
		push_warning("GameManager: ai_engine/config.json not found at: " + config_path)
		return
	var json: JSON = JSON.new()
	var err: int = json.parse(file.get_as_text())
	file.close()
	if err != OK:
		push_error("GameManager: Failed to parse config.json")
		return
	_ai_config = json.data

# ── Server Lifecycle ───────────────────────────────────────────────────────
func launch_llama_server() -> void:
	if _ai_config.is_empty():
		server_failed.emit("config.json not loaded")
		return

	# If server already running, skip launch
	var http: HTTPClient = HTTPClient.new()
	var port: int = _ai_config.get("server", {}).get("port", 8000)
	var host: String = _ai_config.get("server", {}).get("host", "localhost")
	if http.connect_to_host(host, port) == OK:
		print("GameManager: llama-server already running, skipping launch")
		server_ready.emit()
		return

	var binary_path: String = _get_server_binary_path()
	var model_path: String = _get_model_path()
	if binary_path.is_empty() or model_path.is_empty():
		server_failed.emit("Could not resolve server binary or model path")
		return

	var args: Array[String] = ["-m", model_path, "--port", str(port),
		"-c", str(_ai_config.get("server", {}).get("context_size", 2048)),
		"-ngl", str(_ai_config.get("server", {}).get("gpu_layers", 20))]
	_server_pid = OS.create_process(binary_path, args)
	if _server_pid <= 0:
		server_failed.emit("Failed to start llama-server process")
		return

	# Poll health endpoint until ready
	_poll_server_health.call_deferred()

func _poll_server_health() -> void:
	var timeout: float = _ai_config.get("server", {}).get("startup_timeout_sec", 30.0)
	var elapsed: float = 0.0
	while elapsed < timeout:
		AIClient.check_server_health()
		await get_tree().create_timer(1.0).timeout
		elapsed += 1.0
		if AIClient.is_server_online:
			server_ready.emit()
			return
	server_failed.emit("llama-server 啟動逾時（%d 秒），請檢查 binary/model 路徑與系統資源" % int(timeout))

func shutdown_server() -> void:
	if _server_pid > 0:
		OS.kill(_server_pid)
		_server_pid = -1

# ── Path Resolution ────────────────────────────────────────────────────────
func _get_server_binary_path() -> String:
	var platform: String = OS.get_name()
	var key: String
	match platform:
		"Windows": key = "windows"
		"Linux": key = "linux"
		"macOS": key = "macos"
		_: key = "linux"

	var rel_path: String = _ai_config.get("binaries", {}).get(key, "")
	if rel_path.is_empty():
		return ""
	return _resolve_ai_engine_path(rel_path)

func _get_model_path() -> String:
	var rel_path: String = _ai_config.get("model_path", "")
	if rel_path.is_empty():
		return ""
	return _resolve_ai_engine_path(rel_path)

func _resolve_ai_engine_path(relative: String) -> String:
	# Works both in editor and exported builds
	var base: String
	if OS.has_feature("editor"):
		base = ProjectSettings.globalize_path("res://") + "../ai_engine/"
	else:
		base = OS.get_executable_path().get_base_dir() + "/ai_engine/"
	return (base + relative).simplify_path()

# ── State Machine ──────────────────────────────────────────────────────────
func change_state(new_state: GameState) -> void:
	if current_state == new_state:
		return
	current_state = new_state
	game_state_changed.emit(new_state)

# ── Save / Load ────────────────────────────────────────────────────────────
const SAVE_DIR: String = "user://saves/"
const SAVE_VERSION: String = "0.1.0"

func save_game(slot: int = 1) -> void:
	# 確保目錄存在
	DirAccess.make_dir_recursive_absolute(SAVE_DIR)

	# 收集玩家位置
	var player_pos: Vector2 = Vector2.ZERO
	var players: Array[Node] = get_tree().get_nodes_in_group("player")
	if not players.is_empty():
		player_pos = players[0].global_position

	var save_data: Dictionary = {
		"version": SAVE_VERSION,
		"timestamp": int(Time.get_unix_time_from_system()),
		"player": {
			"zone": StoryManager.current_zone,
			"position_x": player_pos.x,
			"position_y": player_pos.y,
		},
		"story": StoryManager.serialize(),
		"quests": QuestManager.serialize(),
		"chapter": ChapterManager.serialize(),
		"time_played_sec": _time_played_sec,
	}

	var path: String = SAVE_DIR + "save_%d.json" % slot
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("GameManager: Cannot write save file: " + path)
		return
	file.store_string(JSON.stringify(save_data, "\t"))
	file.close()
	print("GameManager: Game saved to slot %d" % slot)
	EventBus.hud_message_requested.emit("遊戲已儲存", 2.0)

func load_game(slot: int = 1) -> void:
	var path: String = SAVE_DIR + "save_%d.json" % slot
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_warning("GameManager: Save file not found: " + path)
		return

	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		push_error("GameManager: Failed to parse save file")
		file.close()
		return
	file.close()

	var data: Dictionary = json.data

	# 還原 StoryManager 與 QuestManager 狀態
	# 注意順序：StoryManager 先（含 player_flags），ChapterManager 之後再依 flags 解析
	if data.has("story"):
		StoryManager.deserialize(data["story"])
	if data.has("quests"):
		QuestManager.deserialize(data["quests"])
	if data.has("chapter"):
		ChapterManager.deserialize(data["chapter"])

	# 還原遊戲時間
	if data.has("time_played_sec"):
		_time_played_sec = data["time_played_sec"]

	# 切換到存檔中的區域
	if data.has("player"):
		var player_data: Dictionary = data["player"]
		var zone_id: String = player_data.get("zone", Zones.STARTING)
		var pos_x: float = player_data.get("position_x", 0.0)
		var pos_y: float = player_data.get("position_y", 0.0)
		_pending_load_position = Vector2(pos_x, pos_y)
		EventBus.zone_transition_requested.emit(zone_id, "default")

	print("GameManager: Game loaded from slot %d" % slot)
	EventBus.hud_message_requested.emit("遊戲已載入", 2.0)

## 回主選單：重置 autoload 狀態 + reload 主場景（MainMenu 會自動重新 push）
func return_to_main_menu() -> void:
	# 重置故事 / 任務 / 章節 狀態（傳空 dict 讓 deserialize 套預設值）
	StoryManager.deserialize({})
	QuestManager.deserialize({})
	ChapterManager.deserialize({})
	_time_played_sec = 0.0
	# 中止任何 in-flight AI 請求
	AIClient.abort_current_request()
	# 切回 MAIN_MENU state，reload 主場景讓 zone/player 重置
	change_state(GameState.MAIN_MENU)
	get_tree().reload_current_scene()

func has_save(slot: int = 1) -> bool:
	return FileAccess.file_exists(SAVE_DIR + "save_%d.json" % slot)

func get_save_info(slot: int = 1) -> Dictionary:
	var path: String = SAVE_DIR + "save_%d.json" % slot
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		file.close()
		return {}
	file.close()
	return json.data
