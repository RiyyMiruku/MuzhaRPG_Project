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

# ── Constants ──────────────────────────────────────────────────────────────
const CONFIG_PATH: String = "../../ai_engine/config.json"

# ── Lifecycle ──────────────────────────────────────────────────────────────
func _ready() -> void:
	_load_ai_config()

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
	var port: int = _ai_config.get("server", {}).get("port", 8000)
	var timeout: float = _ai_config.get("server", {}).get("startup_timeout_sec", 30.0)
	var elapsed: float = 0.0
	while elapsed < timeout:
		await get_tree().create_timer(1.0).timeout
		elapsed += 1.0
		# AIClient will handle health checks; emit ready after delay as fallback
	server_ready.emit()

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

# ── Save / Load (Phase 3) ──────────────────────────────────────────────────
func save_game(slot: int = 1) -> void:
	pass  # TODO: Phase 3

func load_game(slot: int = 1) -> void:
	pass  # TODO: Phase 3
