## DialogueUI — NPC 對話介面
## 處理對話框顯示、玩家輸入、打字機動畫與 AI 等待提示。
class_name DialogueUI
extends Control

# ── Signals ────────────────────────────────────────────────────────────────
## AI mode：玩家送出輸入
signal player_submitted_input(text: String)
## Beat mode：玩家按空白/Enter 推進到下一句
signal beat_advance_requested()
## Beat mode：玩家點選 choice button（index 對應 beat.choices 索引）
signal beat_choice_made(choice_index: int)
signal dialogue_closed()

# ── Mode ────────────────────────────────────────────────────────────────────
enum Mode { AI, BEAT }
var _mode: Mode = Mode.AI
## 剛開啟時忽略一幀輸入，避免「按 E 開啟 beat」同一輸入又被當成「推進」
var _just_opened: bool = false

# ── Node References ────────────────────────────────────────────────────────
@onready var _panel: PanelContainer          = $Panel
@onready var _portrait: TextureRect          = $Panel/VBoxOuter/HBox/Portrait
@onready var _name_label: Label              = $Panel/VBoxOuter/HBox/VBox/NameLabel
@onready var _dialogue_text: RichTextLabel   = $Panel/VBoxOuter/HBox/VBox/Scroll/DialogueText
@onready var _input_line: LineEdit           = $Panel/VBoxOuter/InputRow/LineEdit
@onready var _send_btn: Button               = $Panel/VBoxOuter/InputRow/SendButton
@onready var _thinking_dots: AnimationPlayer = $Panel/VBoxOuter/HBox/VBox/ThinkingDots/AnimationPlayer
@onready var _thinking_node: Control         = $Panel/VBoxOuter/HBox/VBox/ThinkingDots
@onready var _input_row: Control             = $Panel/VBoxOuter/InputRow

## ChoiceButtonsContainer 在 _ready 程式生成（避免 .tscn 結構耦合）
var _choice_container: VBoxContainer = null

# ── Typewriter State ───────────────────────────────────────────────────────
var _typewriter_timer: Timer
var _full_text: String = ""
var _displayed_chars: int = 0
var _current_npc_id: String = ""
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

	# 動態建 ChoiceButtonsContainer（同層級在 InputRow 之下）
	_choice_container = VBoxContainer.new()
	_choice_container.name = "ChoiceButtonsContainer"
	_choice_container.add_theme_constant_override("separation", 6)
	_input_row.get_parent().add_child(_choice_container)
	_choice_container.hide()

	# Connect AI signals
	AIClient.response_complete.connect(_on_ai_response_complete)
	AIClient.request_failed.connect(_on_ai_request_failed)

# ── Public API ─────────────────────────────────────────────────────────────
## AI mode：開啟對話讓玩家自由輸入
func open_dialogue(npc_config: NPCConfig) -> void:
	UIManager.pop_all()
	_mode = Mode.AI
	_current_npc_id = npc_config.npc_id
	_name_label.text = npc_config.display_name
	_portrait.texture = npc_config.get_portrait()
	_dialogue_text.text = "（與 %s 對話中，輸入訊息後按 Enter 發送）" % npc_config.display_name
	_input_line.text = ""
	_input_line.editable = true
	_send_btn.disabled = false
	_input_row.show()
	if _choice_container:
		_choice_container.hide()
	hide_thinking_indicator()
	visible = true
	_panel.visible = true
	_input_line.grab_focus()
	GameManager.change_state(GameManager.GameState.DIALOGUE)

## Beat mode：開啟預寫對話（無輸入框，按空白前進）
func open_beat_mode(beat: StoryBeat) -> void:
	UIManager.pop_all()
	_mode = Mode.BEAT
	_just_opened = true
	_current_npc_id = ""
	_name_label.text = ""
	_portrait.texture = null
	_input_row.hide()
	if _choice_container:
		_choice_container.hide()
		_clear_choice_buttons()
	hide_thinking_indicator()
	visible = true
	_panel.visible = true
	GameManager.change_state(GameManager.GameState.DIALOGUE)
	if beat.dialogue_lines.size() > 0:
		show_beat_line(beat.dialogue_lines[0])
	# 等一幀，讓觸發 beat 的 E-press 過去
	await get_tree().process_frame
	_just_opened = false

## Beat mode：顯示一句 dialogue_line（{ "speaker", "text" }）
func show_beat_line(line: Dictionary) -> void:
	var speaker: String = str(line.get("speaker", ""))
	var text: String = str(line.get("text", ""))
	_name_label.text = speaker if speaker != "narrator" else ""
	# narrator 用斜體前綴標註；NPC 直接顯示
	var display_text: String = ("（%s）" % text) if speaker == "narrator" else text
	display_npc_response(display_text)

## Beat mode：顯示 choice buttons（玩家點擊 → emit beat_choice_made(index)）
func show_choices(choices: Array) -> void:
	_clear_choice_buttons()
	if _choice_container == null:
		return
	for i: int in range(choices.size()):
		var c: Dictionary = choices[i]
		var btn: Button = Button.new()
		btn.text = str(c.get("text", "..."))
		btn.pressed.connect(func() -> void: beat_choice_made.emit(i))
		_choice_container.add_child(btn)
	_choice_container.show()

func _clear_choice_buttons() -> void:
	if _choice_container == null:
		return
	for child: Node in _choice_container.get_children():
		child.queue_free()

func close_dialogue() -> void:
	_typewriter_timer.stop()
	# 取消任何進行中的 AI 請求，避免關閉後仍消耗資源 / 收到 stale response
	AIClient.abort_current_request()
	hide_thinking_indicator()
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
		return
	# Beat mode：空白/Enter 推進到下一句（choices 顯示時不收，剛開啟一幀內不收）
	if _mode == Mode.BEAT and not _just_opened and (_choice_container == null or not _choice_container.visible):
		if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
			beat_advance_requested.emit()
			get_viewport().set_input_as_handled()

# ── AI Response Handlers ───────────────────────────────────────────────────
func _on_ai_response_complete(text: String, npc_id: String) -> void:
	if npc_id != _current_npc_id:
		return
	hide_thinking_indicator()
	display_npc_response(text)

func _on_ai_request_failed(error_msg: String) -> void:
	hide_thinking_indicator()
	_dialogue_text.text += "\n[系統] 連線失敗：" + error_msg + "\n"
