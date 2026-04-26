## SpriteSheetLoader — 從預編譯的 spritesheet 載入角色動畫
## 運行時唯一的角色動畫載入路徑。
## 預編譯流程：python scripts/generate_spritesheet.py
class_name SpriteSheetLoader
extends RefCounted

const ATLAS_CONFIG: String = "res://assets/spritesheet_cache/atlas_config.json"
const SPRITESHEET_DIR: String = "res://assets/spritesheet_cache"

## atlas (north/south/east/west) → Godot (up/down/right/left)
const _DIR_MAP: Dictionary = {
	"north": "up", "south": "down", "east": "right", "west": "left"
}

## 從預編譯 spritesheet 載入角色 SpriteFrames。
## character_id: 角色 ID（同 art_source/characters/<id>/ 與 atlas key），如 "chen_ayi"、"player"
## 找不到時 push_error 並返回 null。
static func load_character(character_id: String) -> SpriteFrames:
	var atlas: Dictionary = _read_atlas_config()
	if atlas.is_empty():
		return null

	var characters: Dictionary = atlas.get("characters", {})
	var char_config: Dictionary = characters.get(character_id, {})
	if char_config.is_empty():
		push_error(
			"SpriteSheetLoader: '%s' not in atlas_config. Run scripts/generate_spritesheet.py?"
			% character_id
		)
		return null

	var sheet_path: String = "%s/%s.png" % [SPRITESHEET_DIR, character_id]
	if not ResourceLoader.exists(sheet_path):
		push_error("SpriteSheetLoader: Spritesheet missing: " + sheet_path)
		return null

	var texture: Texture2D = load(sheet_path)
	var frame_size: Array = char_config.get("frame_size", [92, 92])
	var animations: Dictionary = char_config.get("animations", {})

	var frames: SpriteFrames = SpriteFrames.new()
	if frames.has_animation("default"):
		frames.remove_animation("default")

	for anim_name: String in animations.keys():
		var godot_name: String = _convert_anim_name(anim_name)
		if godot_name.is_empty():
			continue

		var info: Dictionary = animations[anim_name]
		var row: int = info.get("row", 0)
		var start: int = info.get("start", 0)
		var end: int = info.get("end", 1)
		var fps: float = info.get("fps", 6.0)
		var loop: bool = info.get("loop", true)

		frames.add_animation(godot_name)
		frames.set_animation_speed(godot_name, fps)
		frames.set_animation_loop(godot_name, loop)

		for col: int in range(start, end):
			var atlas_tex: AtlasTexture = AtlasTexture.new()
			atlas_tex.atlas = texture
			atlas_tex.region = Rect2(
				col * frame_size[0], row * frame_size[1],
				frame_size[0], frame_size[1]
			)
			frames.add_frame(godot_name, atlas_tex)

	return frames

## "idle_north" → "idle_up"、"walk_east" → "walk_right"
static func _convert_anim_name(atlas_name: String) -> String:
	for atlas_dir: String in _DIR_MAP.keys():
		var suffix: String = "_" + atlas_dir
		if atlas_name.ends_with(suffix):
			return atlas_name.replace(suffix, "_" + _DIR_MAP[atlas_dir])
	return ""

static func _read_atlas_config() -> Dictionary:
	if not ResourceLoader.exists(ATLAS_CONFIG):
		push_error("SpriteSheetLoader: atlas_config.json not found at " + ATLAS_CONFIG)
		return {}
	var file: FileAccess = FileAccess.open(ATLAS_CONFIG, FileAccess.READ)
	if file == null:
		push_error("SpriteSheetLoader: Cannot open " + ATLAS_CONFIG)
		return {}
	var json: JSON = JSON.new()
	var err: Error = json.parse(file.get_as_text())
	file.close()
	if err != OK:
		push_error("SpriteSheetLoader: Failed to parse atlas_config.json")
		return {}
	return json.data
