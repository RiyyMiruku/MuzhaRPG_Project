## BaseCharacter — 角色共用移動邏輯
## 玩家與 NPC 均繼承此類別。
class_name BaseCharacter
extends CharacterBody2D

# ── Config ──────────────────────────────────────────────────────────────────
@export var move_speed: float = 80.0

# ── Node References (子類別場景需提供) ────────────────────────────────────
@export var sprite: AnimatedSprite2D

# ── Facing Direction ────────────────────────────────────────────────────────
## 8-direction facing。SpriteFrames 不一定每個方向都有對應動畫,
## _update_animation 會在缺幀時 fallback 到 idle_down。
enum FacingDirection {
	DOWN, UP, LEFT, RIGHT,
	DOWN_RIGHT, DOWN_LEFT, UP_RIGHT, UP_LEFT,
}
var facing: FacingDirection = FacingDirection.DOWN
var is_moving: bool = false

# ── Movement ────────────────────────────────────────────────────────────────
func move_with_input(input_vector: Vector2) -> void:
	if input_vector == Vector2.ZERO:
		velocity = Vector2.ZERO
		is_moving = false
	else:
		velocity = input_vector.normalized() * move_speed
		is_moving = true
		_update_facing(input_vector)
	move_and_slide()
	_update_animation()

func face_toward(target_position: Vector2) -> void:
	var diff: Vector2 = target_position - global_position
	_update_facing(diff)
	_update_animation()

# ── Internals ────────────────────────────────────────────────────────────────
## 8 段角度判斷。Godot 螢幕座標 y 軸往下,Vector2.angle() 範圍 -PI..PI:
## 0 = 右(east),PI/2 = 下(south)。
func _update_facing(direction: Vector2) -> void:
	if direction == Vector2.ZERO:
		return
	var angle: float = direction.angle()
	var sector: int = int(round(angle / (PI / 4.0)))
	# 規範到 [0, 8): -4..4 → 0..7
	sector = ((sector % 8) + 8) % 8
	match sector:
		0: facing = FacingDirection.RIGHT
		1: facing = FacingDirection.DOWN_RIGHT
		2: facing = FacingDirection.DOWN
		3: facing = FacingDirection.DOWN_LEFT
		4: facing = FacingDirection.LEFT
		5: facing = FacingDirection.UP_LEFT
		6: facing = FacingDirection.UP
		7: facing = FacingDirection.UP_RIGHT

func _update_animation() -> void:
	if sprite == null:
		return
	var anim_prefix: String = "walk" if is_moving else "idle"
	var anim_suffix: String
	var fallback_suffix: String
	match facing:
		FacingDirection.DOWN:
			anim_suffix = "_down"
			fallback_suffix = "_down"
		FacingDirection.UP:
			anim_suffix = "_up"
			fallback_suffix = "_up"
		FacingDirection.LEFT:
			anim_suffix = "_left"
			fallback_suffix = "_left"
		FacingDirection.RIGHT:
			anim_suffix = "_right"
			fallback_suffix = "_right"
		FacingDirection.DOWN_RIGHT:
			anim_suffix = "_down_right"
			fallback_suffix = "_down"
		FacingDirection.DOWN_LEFT:
			anim_suffix = "_down_left"
			fallback_suffix = "_down"
		FacingDirection.UP_RIGHT:
			anim_suffix = "_up_right"
			fallback_suffix = "_up"
		FacingDirection.UP_LEFT:
			anim_suffix = "_up_left"
			fallback_suffix = "_up"
	if sprite.sprite_frames == null:
		return
	var anim_name: String = anim_prefix + anim_suffix
	if sprite.sprite_frames.has_animation(anim_name):
		sprite.play(anim_name)
		return
	# 缺 diagonal 時 collapse 回 cardinal
	var fallback_name: String = anim_prefix + fallback_suffix
	if sprite.sprite_frames.has_animation(fallback_name):
		sprite.play(fallback_name)
		return
	# 連 cardinal 都沒(例如 idle-only NPC),最後 fallback
	if sprite.sprite_frames.has_animation("idle_down"):
		sprite.play("idle_down")
