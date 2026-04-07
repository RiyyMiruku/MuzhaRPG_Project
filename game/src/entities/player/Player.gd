## Player — 玩家角色
## WASD / 方向鍵移動，E 鍵與最近的 NPC/物件互動。
class_name Player
extends BaseCharacter

# ── Signals ─────────────────────────────────────────────────────────────────
signal interaction_requested(interactable: Node)

# ── Node References ──────────────────────────────────────────────────────────
@onready var _sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var _interact_area: Area2D    = $InteractArea

# ── State ────────────────────────────────────────────────────────────────────
var _nearby_interactable: Node = null

const PLAYER_SHEET: String = "res://assets/textures/characters/player.png"

func _ready() -> void:
	sprite = _sprite
	add_to_group("player")
	# 載入 spritesheet，若不存在則用佔位精靈
	if _sprite.sprite_frames == null:
		if ResourceLoader.exists(PLAYER_SHEET):
			_sprite.sprite_frames = SpriteSheetLoader.load_character_sheet(PLAYER_SHEET)
		else:
			_sprite.sprite_frames = PlaceholderSprite.generate_sprite_frames(
				Color.CORNFLOWER_BLUE, Color.WHITE, Vector2i(16, 24)
			)
		_sprite.play("idle_down")
	_interact_area.body_entered.connect(_on_body_entered)
	_interact_area.body_exited.connect(_on_body_exited)
	GameManager.game_state_changed.connect(_on_state_changed)

func _physics_process(_delta: float) -> void:
	var input_vec: Vector2 = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	move_with_input(input_vec)

func _on_state_changed(new_state: GameManager.GameState) -> void:
	var can_move: bool = new_state == GameManager.GameState.EXPLORING
	set_physics_process(can_move)
	if not can_move:
		velocity = Vector2.ZERO
		is_moving = false
		_update_animation()

func _unhandled_input(event: InputEvent) -> void:
	if GameManager.current_state == GameManager.GameState.DIALOGUE:
		return
	if event.is_action_pressed("interact") and _nearby_interactable != null:
		interaction_requested.emit(_nearby_interactable)
		EventBus.player_interacted_with.emit(_nearby_interactable)
		# 直接呼叫 NPC 的 interact()
		if _nearby_interactable.has_method("interact"):
			_nearby_interactable.interact(self)
		get_viewport().set_input_as_handled()

# ── Interaction Area ──────────────────────────────────────────────────────────
func _on_body_entered(body: Node) -> void:
	# 優先選最近的可互動物件
	if body.has_method("interact"):
		_nearby_interactable = body

func _on_body_exited(body: Node) -> void:
	if _nearby_interactable == body:
		_nearby_interactable = null
