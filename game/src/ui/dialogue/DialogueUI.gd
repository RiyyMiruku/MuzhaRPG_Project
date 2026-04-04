## DialogueUI — NPC 對話介面
## 處理對話框顯示、玩家輸入、打字機動畫與 AI 等待提示。
class_name DialogueUI
extends Control

# ── Signals ────────────────────────────────────────────────────────────────
signal player_submitted_input(text: String)
signal dialogue_closed()

# ── Node References ────────────────────────────────────────────────────────
@onready var _panel: PanelContainer          = $Panel
@onready var _portrait: TextureRect          = $Panel/VBoxOuter/HBox/Portrait
@onready var _name_label: Label              = $Panel/VBoxOuter/HBox/VBox/NameLabel
@onready var _dialogue_text: RichTextLabel   = $Panel/VBoxOuter/HBox/VBox/Scroll/DialogueText
@onready var _input_line: LineEdit           = $Panel/VBoxOuter/InputRow/LineEdit
@onready var _send_btn: Button               = $Panel/VBoxOuter/InputRow/SendButton
@onready var _thinking_dots: AnimationPlayer = $Panel/VBoxOuter/HBox/VBox/ThinkingDots/AnimationPlayer
@onready var _thinking_node: Control         = $Panel/VBoxOuter/HBox/VBox/ThinkingDots

# ── Typewriter State ───────────────────────────────────────────────────────
var _typewriter_timer: Timer
var _full_text: String = ""
var _displayed_chars: int = 0
const TYPEWRITER_SPEED: float = 0.025   # seconds per character

# ── Lifecycle ──────────────────────────────────────────────────────────────
func _ready() -> void:
	hide()
	_typewriter_timer = Timer.new()
	_typewriter_timer.wait_time = TYPEWRITER_SPEED
	_typewriter_timer.one_shot = false
	_typewriter_timer.timeout.connect(_on_typewriter_tick)
	add_child(_typewriter_timer)

	_send_btn.pressed.connect(_on_send_pressed)
	_input_line.text_submitted.connect(_on_line_edit_submitted)

	# Connect AI signals
	AIClient.response_complete.connect(_on_ai_response_complete)
	AIClient.request_failed.connect(_on_ai_request_failed)

# ── Public API ─────────────────────────────────────────────────────────────
func open_dialogue(npc_config: NPCConfig) -> void:
	print("DialogueUI: open_dialogue called for ", npc_config.display_name)
	_name_label.text = npc_config.display_name
	_portrait.texture = npc_config.portrait_texture
	_dialogue_text.text = "（與 %s 對話中，輸入訊息後按 Enter 發送）" % npc_config.display_name
	_input_line.text = ""
	_input_line.editable = true
	_send_btn.disabled = false
	hide_thinking_indicator()
	visible = true
	_panel.visible = true
	print("DialogueUI: visible=", visible, " panel.visible=", _panel.visible, " size=", size)
	_input_line.grab_focus()
	GameManager.change_state(GameManager.GameState.DIALOGUE)

func close_dialogue() -> void:
	_typewriter_timer.stop()
	hide()
	GameManager.change_state(GameManager.GameState.EXPLORING)
	dialogue_closed.emit()
	EventBus.npc_interaction_ended.emit()

func show_thinking_indicator() -> void:
	_thinking_node.show()
	if _thinking_dots.has_animation("thinking"):
		_thinking_dots.play("thinking")
	_input_line.editable = false
	_send_btn.disabled = true

func hide_thinking_indicator() -> void:
	_thinking_node.hide()
	if _thinking_dots.is_playing():
		_thinking_dots.stop()
	_input_line.editable = true
	_send_btn.disabled = false

## 顯示完整的 NPC 回應並觸發打字機動畫
func display_npc_response(text: String) -> void:
	_dialogue_text.text = ""
	_full_text = text
	_displayed_chars = 0
	_typewriter_timer.start()

# ── Typewriter ─────────────────────────────────────────────────────────────
func _on_typewriter_tick() -> void:
	if _displayed_chars >= _full_text.length():
		_typewriter_timer.stop()
		return
	_displayed_chars += 1
	_dialogue_text.text = _full_text.substr(0, _displayed_chars)

# ── Input Handlers ─────────────────────────────────────────────────────────
func _on_send_pressed() -> void:
	_submit_input(_input_line.text)

func _on_line_edit_submitted(text: String) -> void:
	_submit_input(text)

func _submit_input(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty():
		return
	_input_line.text = ""
	# 顯示玩家訊息
	_dialogue_text.text += "\n[玩家] " + text + "\n"
	show_thinking_indicator()
	player_submitted_input.emit(text)

func _input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("pause"):
		close_dialogue()
		get_viewport().set_input_as_handled()

# ── AI Response Handlers ───────────────────────────────────────────────────
func _on_ai_response_complete(text: String, _npc_id: String) -> void:
	hide_thinking_indicator()
	display_npc_response(text)

func _on_ai_request_failed(error_msg: String) -> void:
	hide_thinking_indicator()
	_dialogue_text.text += "\n[系統] 連線失敗：" + error_msg + "\n"
