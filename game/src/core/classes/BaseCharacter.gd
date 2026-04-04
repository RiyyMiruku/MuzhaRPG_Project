## BaseCharacter — 角色共用移動邏輯
## 玩家與 NPC 均繼承此類別。
class_name BaseCharacter
extends CharacterBody2D

# ── Config ──────────────────────────────────────────────────────────────────
@export var move_speed: float = 80.0

# ── Node References (子類別場景需提供) ────────────────────────────────────
@export var sprite: AnimatedSprite2D

# ── Facing Direction ────────────────────────────────────────────────────────
enum FacingDirection { DOWN, UP, LEFT, RIGHT }
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
func _update_facing(direction: Vector2) -> void:
	if abs(direction.x) > abs(direction.y):
		facing = FacingDirection.RIGHT if direction.x > 0 else FacingDirection.LEFT
	else:
		facing = FacingDirection.DOWN if direction.y > 0 else FacingDirection.UP

func _update_animation() -> void:
	if sprite == null:
		return
	var anim_prefix: String = "walk" if is_moving else "idle"
	var anim_suffix: String
	match facing:
		FacingDirection.DOWN:  anim_suffix = "_down"
		FacingDirection.UP:    anim_suffix = "_up"
		FacingDirection.LEFT:  anim_suffix = "_left"
		FacingDirection.RIGHT: anim_suffix = "_right"
	var anim_name: String = anim_prefix + anim_suffix
	if sprite.sprite_frames and sprite.sprite_frames.has_animation(anim_name):
		sprite.play(anim_name)
	elif sprite.sprite_frames and sprite.sprite_frames.has_animation("idle_down"):
		sprite.play("idle_down")
