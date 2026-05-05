## Smoke test for SpriteSheetLoader (run from Godot editor with F6).
## Requires the test_dummy fixture: `uv run python scripts/create_dummy_character.py`.
## On pass: prints "PASS: ..." and shows a red-tinted dummy sprite playing.
## On fail: prints "FAIL: ..." with diagnostic details.
extends Node2D

func _ready() -> void:
	var sprite: AnimatedSprite2D = $AnimatedSprite2D

	# 1. Load via SpriteSheetLoader
	var frames: SpriteFrames = SpriteSheetLoader.load_character("test_dummy")
	if frames == null:
		push_error("FAIL: SpriteSheetLoader returned null")
		print("FAIL: SpriteSheetLoader returned null")
		return

	# 2. Check idle_down (south → down via _DIR_MAP)
	if not frames.has_animation("idle_down"):
		push_error("FAIL: SpriteFrames missing animation 'idle_down'")
		print("FAIL: SpriteFrames missing animation 'idle_down'")
		return

	# 3. Check idle_right (east → right via _DIR_MAP)
	if not frames.has_animation("idle_right"):
		push_error("FAIL: SpriteFrames missing animation 'idle_right'")
		print("FAIL: SpriteFrames missing animation 'idle_right'")
		return

	# 4. Report frame counts
	var count_down: int = frames.get_frame_count("idle_down")
	var count_right: int = frames.get_frame_count("idle_right")
	print("idle_down has %d frames" % count_down)
	print("idle_right has %d frames" % count_right)

	# 5. Assign + play on the AnimatedSprite2D child
	sprite.sprite_frames = frames
	sprite.animation = "idle_down"
	sprite.play()

	# 6. Final result
	print("PASS: SpriteSheetLoader smoke test ok")
