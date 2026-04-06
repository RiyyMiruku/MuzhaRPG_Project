extends Node

# ── Signals ────────────────────────────────────────────────────────────────
signal response_complete(full_text: String, npc_id: String)
signal request_failed(error_msg: String)
signal server_status_changed(is_online: bool)

# ── Config ──────────────────────────────────────────────────────────────────
var server_url: String = "http://127.0.0.1:8000"
var is_server_online: bool = false
var default_temperature: float = 0.7
var default_max_tokens: int = 200
var request_timeout_sec: float = 30.0

# ── Internal ────────────────────────────────────────────────────────────────
var _http: HTTPRequest          # 用於 AI query
var _health_http: HTTPRequest   # 用於 health check（獨立）
var _current_npc_id: String = ""
var _is_busy: bool = false

func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = request_timeout_sec
	add_child(_http)
	_http.request_completed.connect(_on_query_completed)

	_health_http = HTTPRequest.new()
	_health_http.timeout = 5.0
	add_child(_health_http)
	_health_http.request_completed.connect(_on_health_completed)

	await get_tree().process_frame
	_sync_server_url()
	# 啟動時自動檢查伺服器是否在線
	check_server_health()

func _sync_server_url() -> void:
	var config: Dictionary = GameManager._ai_config
	if config.is_empty():
		return
	var host: String = config.get("server", {}).get("host", "localhost")
	var port: int = config.get("server", {}).get("port", 8000)
	server_url = "http://%s:%d" % [host, port]

# ── Health Check ────────────────────────────────────────────────────────────
func check_server_health() -> void:
	var err: int = _health_http.request(server_url + "/health")
	if err != OK:
		_set_online(false)

func _on_health_completed(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	if result == HTTPRequest.RESULT_SUCCESS and response_code == 200:
		_set_online(true)
		print("AIClient: 伺服器已連線 ✓")
	else:
		_set_online(false)
		print("AIClient: 伺服器未回應 (HTTP %d)" % response_code)

# ── Core Query ──────────────────────────────────────────────────────────────
func query(npc_config: Resource, user_input: String, context: Dictionary) -> void:
	if _is_busy:
		push_warning("AIClient: Already processing a request, ignoring new query")
		return
	if not is_server_online:
		# 先嘗試一次 health check，也許伺服器剛啟動
		request_failed.emit("AI 伺服器尚未連線，請確認 llama-server 已啟動")
		check_server_health()
		return

	_is_busy = true
	_current_npc_id = npc_config.npc_id

	var payload: Dictionary = _build_chat_payload(npc_config, user_input, context)
	var body: String = JSON.stringify(payload)
	var headers: PackedStringArray = ["Content-Type: application/json"]

	var err: int = _http.request(
		server_url + "/v1/chat/completions",
		headers,
		HTTPClient.METHOD_POST,
		body
	)
	if err != OK:
		_is_busy = false
		request_failed.emit("HTTP 請求發送失敗 (error %d)" % err)

func _on_query_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_is_busy = false

	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		_set_online(false)
		request_failed.emit("伺服器回應錯誤 (HTTP %d)" % response_code)
		return

	_set_online(true)

	var json: JSON = JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		request_failed.emit("無法解析 AI 回應 JSON")
		return

	var data: Dictionary = json.data
	var content: String = ""
	var choices: Array = data.get("choices", [])

	if not choices.is_empty():
		var message: Dictionary = choices[0].get("message", {})
		content = str(message.get("content", ""))

	# 清除所有 <think>...</think> 標籤
	while content.contains("<think>"):
		var think_start: int = content.find("<think>")
		var think_end: int = content.find("</think>")
		if think_end != -1:
			content = content.substr(0, think_start) + content.substr(think_end + 8)
		else:
			# </think> 不存在 = 思考被截斷，移除從 <think> 開始的所有內容
			content = content.substr(0, think_start)
		content = content.strip_edges()

	if content.is_empty() or content == "null":
		request_failed.emit("AI 回應為空，請重試")
		return

	# Save to conversation history
	StoryManager.add_conversation_turn(_current_npc_id, "assistant", content)

	var npc_id: String = _current_npc_id
	_current_npc_id = ""
	response_complete.emit(content, npc_id)

# ── Payload Builder ─────────────────────────────────────────────────────────
func _build_chat_payload(npc_config: Resource, user_input: String, context: Dictionary) -> Dictionary:
	var system_content: String = npc_config.system_prompt + "\n\n" + _build_context_string(context)

	var messages: Array[Dictionary] = [{"role": "system", "content": system_content}]

	# Inject conversation history (capped to memory_turns)
	var history: Array = context.get("conversation_history", [])
	var max_turns: int = npc_config.conversation_memory_turns if "conversation_memory_turns" in npc_config else 6
	var start: int = max(0, history.size() - max_turns * 2)
	for i in range(start, history.size()):
		messages.append(history[i])

	# Add current user message and save to history
	messages.append({"role": "user", "content": user_input})
	StoryManager.add_conversation_turn(npc_config.npc_id, "user", user_input)

	# 預填空思考區塊，阻止模型進入 thinking 模式
	messages.append({"role": "assistant", "content": "<think>\n</think>\n", "prefix": true})

	return {
		"model": "default",
		"messages": messages,
		"max_tokens": npc_config.max_response_tokens if "max_response_tokens" in npc_config else default_max_tokens,
		"temperature": npc_config.base_temperature if "base_temperature" in npc_config else default_temperature,
		"stream": false,
	}

func _build_context_string(context: Dictionary) -> String:
	var rel: int = context.get("relationship", 0)
	var rel_tag: String = "stranger"
	if rel >= 60:     rel_tag = "close_friend"
	elif rel >= 30:   rel_tag = "acquaintance"
	elif rel >= 10:   rel_tag = "seen_before"
	elif rel <= -30:  rel_tag = "unfriendly"
	var ctx: String = "[Context] time=%s, zone=%s, rel=%s" % [
		context.get("time_of_day", ""),
		context.get("zone_display", ""),
		rel_tag]
	var events: Array = context.get("recent_events", [])
	if not events.is_empty():
		ctx += ", recent=" + ",".join(events)
	return ctx

# ── Internal Helpers ─────────────────────────────────────────────────────────
func _set_online(online: bool) -> void:
	if is_server_online != online:
		is_server_online = online
		server_status_changed.emit(online)
		if online:
			EventBus.ai_server_online.emit()
		else:
			EventBus.ai_server_offline.emit()

func abort_current_request() -> void:
	if _is_busy:
		_http.cancel_request()
		_is_busy = false
		_current_npc_id = ""
