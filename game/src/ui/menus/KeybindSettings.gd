## KeybindSettings — 按鍵綁定設定面板
class_name KeybindSettings
extends Control

const REBINDABLE_ACTIONS: Dictionary = {
	"move_up":        "Move Up",
	"move_down":      "Move Down",
	"move_left":      "Move Left",
	"move_right":     "Move Right",
	"interact":       "Interact",
	"pause":          "Pause",
	"toggle_map":     "Map",
	"toggle_journal": "Journal",
}

const SAVE_PATH: String = "user://keybinds.json"

@onready var _list: VBoxContainer = $Panel/Scroll/VBox
@onready var _status_label: Label = $Panel/StatusLabel
@onready var _close_btn: Button   = $Panel/CloseButton

var _waiting_for_key: String = ""
var _waiting_button: Button = null

func _ready() -> void:
	UIManager.register("KeybindSettings", self)
	_close_btn.pressed.connect(_on_close)
	load_keybinds()
	visibility_changed.connect(_on_visibility_changed)

func _on_visibility_changed() -> void:
	if visible:
		_rebuild_list()

func _input(event: InputEvent) -> void:
	if not visible:
		return
	# 攔截按鍵重新綁定
	if not _waiting_for_key.is_empty() and event is InputEventKey and event.is_pressed():
		_rebind_action(_waiting_for_key, event as InputEventKey)
		get_viewport().set_input_as_handled()
		return
	# ESC 返回上一層（PauseMenu）
	if event.is_action_pressed("pause"):
		_on_close()
		get_viewport().set_input_as_handled()
		return

func open() -> void:
	_rebuild_list()
	UIManager.push("KeybindSettings")

func _on_close() -> void:
	_waiting_for_key = ""
	_waiting_button = null
	UIManager.pop()  # 回到 PauseMenu

# ── UI 列表 ──────────────────────────────────────────────────────────────────
func _rebuild_list() -> void:
	for child: Node in _list.get_children():
		child.queue_free()

	for action: String in REBINDABLE_ACTIONS:
		var row: HBoxContainer = HBoxContainer.new()

		var label: Label = Label.new()
		label.text = REBINDABLE_ACTIONS[action]
		label.custom_minimum_size = Vector2(120, 0)
		label.add_theme_font_size_override("font_size", 12)
		row.add_child(label)

		var btn: Button = Button.new()
		btn.text = _get_key_name(action)
		btn.custom_minimum_size = Vector2(100, 28)
		btn.add_theme_font_size_override("font_size", 12)
		btn.pressed.connect(_on_rebind_pressed.bind(action, btn))
		row.add_child(btn)

		_list.add_child(row)

func _on_rebind_pressed(action: String, btn: Button) -> void:
	_waiting_for_key = action
	_waiting_button = btn
	btn.text = "Press a key..."
	_status_label.text = "Press any key to rebind"

func _rebind_action(action: String, event: InputEventKey) -> void:
	var old_events: Array[InputEvent] = InputMap.action_get_events(action)
	for old_event: InputEvent in old_events:
		InputMap.action_erase_event(action, old_event)
	InputMap.action_add_event(action, event)

	_waiting_for_key = ""
	_status_label.text = "Saved!"
	if _waiting_button:
		_waiting_button.text = _get_key_name(action)
		_waiting_button = null
	save_keybinds()

func _get_key_name(action: String) -> String:
	var events: Array[InputEvent] = InputMap.action_get_events(action)
	for evt: InputEvent in events:
		if evt is InputEventKey:
			return (evt as InputEventKey).as_text()
	return "---"

# ── 存讀設定 ──────────────────────────────────────────────────────────────────
func save_keybinds() -> void:
	var data: Dictionary = {}
	for action: String in REBINDABLE_ACTIONS:
		var events: Array[InputEvent] = InputMap.action_get_events(action)
		var keys: Array[Dictionary] = []
		for evt: InputEvent in events:
			if evt is InputEventKey:
				var key_evt: InputEventKey = evt as InputEventKey
				keys.append({
					"physical_keycode": key_evt.physical_keycode,
					"keycode": key_evt.keycode,
					"unicode": key_evt.unicode,
				})
		data[action] = keys

	var file: FileAccess = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(data, "\t"))
		file.close()

func load_keybinds() -> void:
	var file: FileAccess = FileAccess.open(SAVE_PATH, FileAccess.READ)
	if file == null:
		return
	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		file.close()
		return
	file.close()

	var data: Dictionary = json.data
	for action: String in data:
		if not InputMap.has_action(action):
			continue
		var old_events: Array[InputEvent] = InputMap.action_get_events(action)
		for old_evt: InputEvent in old_events:
			InputMap.action_erase_event(action, old_evt)
		var keys: Array = data[action]
		for key_data: Variant in keys:
			var key_dict: Dictionary = key_data as Dictionary
			var evt: InputEventKey = InputEventKey.new()
			evt.physical_keycode = key_dict.get("physical_keycode", 0) as Key
			evt.keycode = key_dict.get("keycode", 0) as Key
			evt.unicode = key_dict.get("unicode", 0)
			InputMap.action_add_event(action, evt)
