## UIManager — UI 畫面堆疊管理器
## 維護一個面板堆疊，只有最頂層面板可見且接收輸入。
## 所有 UI 面板統一透過 UIManager 開關，不再各自管理。
extends Node

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS

# ── Signals ─────────────────────────────────────────────────────────────────
signal stack_changed()

# ── State ───────────────────────────────────────────────────────────────────
var _stack: Array[Control] = []
var _registered: Dictionary = {}  # name -> Control

## 是否有任何面板開啟中
var is_any_open: bool:
	get: return not _stack.is_empty()

## 當前最頂層面板名稱
var current_panel: String:
	get:
		if _stack.is_empty():
			return ""
		return _stack.back().name

# ── 註冊 ───────────────────────────────────────────────────────────────────
## 面板在 _ready 時呼叫此方法註冊自己
func register(panel_name: String, panel: Control) -> void:
	_registered[panel_name] = panel
	panel.hide()

## 取得已註冊的面板
func get_panel(panel_name: String) -> Control:
	return _registered.get(panel_name, null)

# ── 堆疊操作 ───────────────────────────────────────────────────────────────
## 將面板推入堆疊頂部（前一個面板會被隱藏）
func push(panel_name: String) -> void:
	var panel: Control = _registered.get(panel_name, null)
	if panel == null:
		push_warning("UIManager: panel not registered: " + panel_name)
		return
	if not _stack.is_empty() and _stack.back() == panel:
		return  # 已經在頂部

	# 隱藏當前頂部
	if not _stack.is_empty():
		_stack.back().hide()

	_stack.append(panel)
	panel.show()
	_update_game_state()
	stack_changed.emit()

## 關閉最頂層面板，回到前一層
func pop() -> void:
	if _stack.is_empty():
		return

	var top: Control = _stack.pop_back()
	top.hide()

	# 顯示新的頂部
	if not _stack.is_empty():
		_stack.back().show()

	_update_game_state()
	stack_changed.emit()

## 關閉所有面板，回到遊戲
func pop_all() -> void:
	while not _stack.is_empty():
		var panel: Control = _stack.pop_back()
		panel.hide()
	_update_game_state()
	stack_changed.emit()

## 替換頂層面板（不影響下層）
func replace(panel_name: String) -> void:
	if not _stack.is_empty():
		_stack.back().hide()
		_stack.pop_back()
	push(panel_name)

## 切換面板（開著就關，關著就開）
func toggle(panel_name: String) -> void:
	var panel: Control = _registered.get(panel_name, null)
	if panel == null:
		return
	if not _stack.is_empty() and _stack.back() == panel:
		pop()
	else:
		# 如果是同級面板（非子面板），先清空堆疊
		pop_all()
		push(panel_name)

# ── 內部 ───────────────────────────────────────────────────────────────────
func _update_game_state() -> void:
	if _stack.is_empty():
		get_tree().paused = false
		GameManager.change_state(GameManager.GameState.EXPLORING)
	else:
		get_tree().paused = true
		GameManager.change_state(GameManager.GameState.PAUSED)

## 攔截輸入：有面板開啟時，阻止遊戲操作
func _input(event: InputEvent) -> void:
	if _stack.is_empty():
		return
	# 讓頂層面板的 _input 先處理，其餘一律攔截
	if event is InputEventKey or event is InputEventMouseButton:
		# 不攔截 — 讓事件繼續傳給頂層面板
		# 但標記為已處理，防止傳到遊戲場景
		pass

func _unhandled_input(event: InputEvent) -> void:
	# 有面板開啟時，攔截所有未處理的輸入
	if not _stack.is_empty():
		get_viewport().set_input_as_handled()
