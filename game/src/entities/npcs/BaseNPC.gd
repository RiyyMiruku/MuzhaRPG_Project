## BaseNPC — NPC 基底類別
## 綁定一個 NPCConfig 資源，並在玩家靠近時顯示互動提示、開啟對話。
class_name BaseNPC
extends BaseCharacter

# ── Config ───────────────────────────────────────────────────────────────────
@export var npc_config: NPCConfig

# ── Node References ──────────────────────────────────────────────────────────
@onready var _sprite: AnimatedSprite2D    = $AnimatedSprite2D
@onready var _prompt_label: Label         = $InteractionPrompt
@onready var _detect_area: Area2D         = $DetectArea

# ── State ────────────────────────────────────────────────────────────────────
var _dialogue_ui: DialogueUI = null
var _conversation_active: bool = false

func _ready() -> void:
	sprite = _sprite
	move_speed = 0.0   # NPC 預設靜止

	# 若沒有美術資源，自動產生橘色佔位精靈
	if _sprite.sprite_frames == null:
		_sprite.sprite_frames = PlaceholderSprite.generate_sprite_frames(
			Color.ORANGE_RED, Color.YELLOW, Vector2i(16, 24)
		)
	_sprite.play("idle_down")

	if npc_config == null:
		push_warning("BaseNPC: npc_config 未設定於 " + name)
		return

	_prompt_label.text = "按 [E] 對話"
	_prompt_label.hide()

	_detect_area.body_entered.connect(_on_player_entered)
	_detect_area.body_exited.connect(_on_player_exited)

## 外部呼叫（通常由 Player 觸發）— 開啟對話
func interact(_player: Node) -> void:
	if _conversation_active or npc_config == null:
		return
	_conversation_active = true
	_prompt_label.hide()

	# 尋找場景中的 DialogueUI
	_dialogue_ui = _find_dialogue_ui()
	if _dialogue_ui == null:
		push_error("BaseNPC: 找不到 DialogueUI 節點")
		_conversation_active = false
		return

	face_toward(_player.global_position)
	_dialogue_ui.open_dialogue(npc_config)
	# 安全連接（避免重複連接錯誤）
	if not _dialogue_ui.player_submitted_input.is_connected(_on_player_input):
		_dialogue_ui.player_submitted_input.connect(_on_player_input)
	if not _dialogue_ui.dialogue_closed.is_connected(_on_dialogue_closed):
		_dialogue_ui.dialogue_closed.connect(_on_dialogue_closed, CONNECT_ONE_SHOT)
	EventBus.npc_interaction_started.emit(self)

func _on_player_input(text: String) -> void:
	var context: Dictionary = StoryManager.build_ai_context(npc_config.npc_id)
	AIClient.query(npc_config, text, context)

func _on_dialogue_closed() -> void:
	_conversation_active = false
	# 清理 signal 連接
	if _dialogue_ui and _dialogue_ui.player_submitted_input.is_connected(_on_player_input):
		_dialogue_ui.player_submitted_input.disconnect(_on_player_input)

# ── Detect Area ───────────────────────────────────────────────────────────────
func _on_player_entered(body: Node) -> void:
	if body is Player:
		_prompt_label.show()

func _on_player_exited(body: Node) -> void:
	if body is Player:
		_prompt_label.hide()

# ── Helpers ───────────────────────────────────────────────────────────────────
func _find_dialogue_ui() -> DialogueUI:
	# 搜尋 UILayer 下的 DialogueUI 節點
	var ui_layer: Node = get_tree().current_scene.find_child("UILayer", true, false)
	if ui_layer == null:
		return null
	return ui_layer.find_child("DialogueUI", true, false) as DialogueUI
