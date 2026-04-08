## SpriteSheetLoader — 從 spritesheet PNG 自動建立 SpriteFrames
## 支援 N 列 × M 行的標準格子 spritesheet。
## 也支援從預編譯的 atlas_config.json 快速加載
class_name SpriteSheetLoader
extends RefCounted

const PRECOMPILED_CONFIG: String = "res://assets/spritesheet_cache/atlas_config.json"

## 從 spritesheet 建立 SpriteFrames
## texture_path: 圖片資源路徑（如 "res://assets/textures/characters/player.png"）
## columns: 每行幾幀
## rows: 共幾行
## row_mapping: 每行對應的動畫名稱陣列，如 ["idle_down", "walk_down", ...]
## idle_frames: 每行前幾幀為 idle（其餘為 walk）
static func load_spritesheet(
	texture_path: String,
	columns: int,
	rows: int,
	row_mapping: Array[Dictionary],
	fps: float = 8.0
) -> SpriteFrames:
	var texture: Texture2D = remove_checker_background(texture_path)
	if texture == null:
		push_error("SpriteSheetLoader: Cannot load texture: " + texture_path)
		return null

	var img_width: int = texture.get_width()
	var img_height: int = texture.get_height()
	var frame_w: int = img_width / columns
	var frame_h: int = img_height / rows

	var frames: SpriteFrames = SpriteFrames.new()
	# 移除預設動畫
	if frames.has_animation("default"):
		frames.remove_animation("default")

	for row_info: Dictionary in row_mapping:
		var row: int = row_info["row"]
		var anim_name: String = row_info["animation"]
		var start_col: int = row_info.get("start", 0)
		var end_col: int = row_info.get("end", columns)
		var anim_fps: float = row_info.get("fps", fps)
		var loop: bool = row_info.get("loop", true)

		frames.add_animation(anim_name)
		frames.set_animation_speed(anim_name, anim_fps)
		frames.set_animation_loop(anim_name, loop)

		for col: int in range(start_col, end_col):
			var atlas: AtlasTexture = AtlasTexture.new()
			atlas.atlas = texture
			atlas.region = Rect2(col * frame_w, row * frame_h, frame_w, frame_h)
			frames.add_frame(anim_name, atlas)

	return frames

## 移除灰白格子背景（AI 生圖工具常見問題）
## 偵測角落像素的背景色，將相近顏色設為透明
static func remove_checker_background(texture_path: String) -> Texture2D:
	var img: Image = Image.load_from_file(
		ProjectSettings.globalize_path(texture_path)
	)
	if img == null:
		img = load(texture_path).get_image()
	if img == null:
		return load(texture_path)

	img.convert(Image.FORMAT_RGBA8)
	var w: int = img.get_width()
	var h: int = img.get_height()

	# 取四個角落的像素作為背景色樣本
	var bg_colors: Array[Color] = []
	var corners: Array[Vector2i] = [
		Vector2i(0, 0), Vector2i(w - 1, 0),
		Vector2i(0, h - 1), Vector2i(w - 1, h - 1),
		Vector2i(1, 0), Vector2i(0, 1),  # 格子的另一色
		Vector2i(1, 1),
	]
	for c: Vector2i in corners:
		var col: Color = img.get_pixelv(c)
		var already: bool = false
		for existing: Color in bg_colors:
			if col.is_equal_approx(existing):
				already = true
				break
		if not already and col.a > 0.5:
			bg_colors.append(col)

	# 過濾：只保留灰色系（R≈G≈B，且亮度 > 0.5）的背景色
	var grey_bg: Array[Color] = []
	for col: Color in bg_colors:
		var diff: float = max(abs(col.r - col.g), max(abs(col.g - col.b), abs(col.r - col.b)))
		if diff < 0.1 and col.v > 0.5:
			grey_bg.append(col)

	if grey_bg.is_empty():
		return load(texture_path)

	# 將背景色像素設為透明
	var threshold: float = 0.06
	for x: int in range(w):
		for y: int in range(h):
			var px: Color = img.get_pixel(x, y)
			if px.a < 0.1:
				continue
			for bg: Color in grey_bg:
				if abs(px.r - bg.r) < threshold and abs(px.g - bg.g) < threshold and abs(px.b - bg.b) < threshold:
					img.set_pixel(x, y, Color(0, 0, 0, 0))
					break

	return ImageTexture.create_from_image(img)

## 預設的 4 方向角色 spritesheet 載入
## 格式: 6 列 × 4 行, 排列為 [下, 右, 左, 上]
## 每行前 2 幀 = idle, 後 4 幀 = walk
## 標準角色 spritesheet 規格：
## 6 列 × 4 行, 排列為 [下, 右, 左, 上]
## 每行第 1 格 = idle（靜止，單幀），第 2~6 格 = walk（走路，5 幀循環）
static func load_character_sheet(texture_path: String) -> SpriteFrames:
	var mapping: Array[Dictionary] = [
		# Row 0: 正面（下）
		{"row": 0, "animation": "idle_down",  "start": 0, "end": 1, "fps": 1.0, "loop": false},
		{"row": 0, "animation": "walk_down",  "start": 1, "end": 6, "fps": 8.0},
		# Row 1: 側面右
		{"row": 1, "animation": "idle_right", "start": 0, "end": 1, "fps": 1.0, "loop": false},
		{"row": 1, "animation": "walk_right", "start": 1, "end": 6, "fps": 8.0},
		# Row 2: 側面左
		{"row": 2, "animation": "idle_left",  "start": 0, "end": 1, "fps": 1.0, "loop": false},
		{"row": 2, "animation": "walk_left",  "start": 1, "end": 6, "fps": 8.0},
		# Row 3: 背面（上）
		{"row": 3, "animation": "idle_up",    "start": 0, "end": 1, "fps": 1.0, "loop": false},
		{"row": 3, "animation": "walk_up",    "start": 1, "end": 6, "fps": 8.0},
	]
	return load_spritesheet(texture_path, 6, 4, mapping)

## 從角色資料夾的 metadata.json 載入序列圖動畫
## 支援多個方向(-north, -south, -east, -west) 和多個動畫狀態
## character_dir_path: 角色資料夾路徑，如 "res://assets/textures/characters/Chen_Ayi_-_Market_Vendor"
static func load_from_metadata(character_dir_path: String) -> SpriteFrames:
	var metadata_path: String = character_dir_path + "/metadata.json"
	var file: FileAccess = FileAccess.open(metadata_path, FileAccess.READ)
	if file == null:
		push_error("SpriteSheetLoader: metadata.json not found at: " + metadata_path)
		return null

	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		push_error("SpriteSheetLoader: Failed to parse metadata.json")
		file.close()
		return null
	file.close()

	var data: Dictionary = json.data
	var frames_data: Dictionary = data.get("frames", {})
	var animations_dict: Dictionary = frames_data.get("animations", {})

	if animations_dict.is_empty():
		push_error("SpriteSheetLoader: No animations found in metadata")
		return null

	var sprite_frames: SpriteFrames = SpriteFrames.new()
	if sprite_frames.has_animation("default"):
		sprite_frames.remove_animation("default")

	# 方向對應表 (north, south, east, west -> 上、下、右、左)
	var direction_map: Dictionary = {
		"north": "_up",
		"south": "_down",
		"west": "_left",
		"east": "_right"
	}

	# 遍歷每個動畫
	for anim_name: String in animations_dict.keys():
		var anim_data: Dictionary = animations_dict[anim_name]

		# 遍歷每個方向
		for direction: String in direction_map.keys():
			if not direction in anim_data:
				continue

			var frame_paths: Array = anim_data[direction]
			var full_anim_name: String = _sanitize_animation_name(anim_name) + direction_map[direction]

			sprite_frames.add_animation(full_anim_name)
			sprite_frames.set_animation_speed(full_anim_name, 6.0)  # 默認 6 FPS
			sprite_frames.set_animation_loop(full_anim_name, true)

			# 載入每一幀
			for frame_path: String in frame_paths:
				var full_path: String = character_dir_path + "/" + frame_path
				if not ResourceLoader.exists(full_path):
					push_warning("SpriteSheetLoader: Frame not found: " + full_path)
					continue

				var texture: Texture2D = load(full_path)
				if texture != null:
					sprite_frames.add_frame(full_anim_name, texture)

	if sprite_frames.get_animation_names().size() == 0:
		push_error("SpriteSheetLoader: No valid animations loaded")
		return null

	return sprite_frames

## 清理動畫名稱（移除特殊字符和時間戳）
static func _sanitize_animation_name(name: String) -> String:
	# 移除 "-xxxxx" 形式的時間戳
	var base_name: String = name.split("-")[0]
	# 轉換小寫並替換空格為下劃線
	return base_name.to_lower().replace(" ", "_").replace(".", "")

# ── 預編譯 Spritesheet 加載 ──────────────────────────────────────────────────
## 從預編譯的 atlas_config.json + spritesheet PNG 快速加載
## 推薦用於發佈版本（性能最優，<100ms）
static func load_precompiled_spritesheet(character_name: String) -> SpriteFrames:
	if not ResourceLoader.exists(PRECOMPILED_CONFIG):
		push_warning("SpriteSheetLoader: atlas_config.json not found")
		return null

	var file: FileAccess = FileAccess.open(PRECOMPILED_CONFIG, FileAccess.READ)
	if file == null:
		push_error("SpriteSheetLoader: Cannot open atlas_config.json")
		return null

	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		push_error("SpriteSheetLoader: Failed to parse atlas_config.json")
		file.close()
		return null
	file.close()

	var config: Dictionary = json.data
	var characters: Dictionary = config.get("characters", {})

	# 尋找角色（可能需要模糊匹配）
	var char_config: Dictionary = characters.get(character_name, {})
	if char_config.is_empty():
		# 試試看用基礎名稱匹配（去掉尾碼）
		for key: String in characters.keys():
			if key.begins_with(character_name):
				char_config = characters[key]
				break

	if char_config.is_empty():
		push_error("SpriteSheetLoader: Character not found in atlas_config: " + character_name)
		return null

	# 載入 Spritesheet PNG
	var spritesheet_path: String = "res://assets/spritesheet_cache/%s.png" % character_name
	if not ResourceLoader.exists(spritesheet_path):
		push_error("SpriteSheetLoader: Spritesheet not found: " + spritesheet_path)
		return null

	var texture: Texture2D = load(spritesheet_path)
	if texture == null:
		push_error("SpriteSheetLoader: Failed to load texture: " + spritesheet_path)
		return null

	var frame_size: Array = char_config.get("frame_size", [92, 92])
	var animations: Dictionary = char_config.get("animations", {})

	var frames: SpriteFrames = SpriteFrames.new()
	if frames.has_animation("default"):
		frames.remove_animation("default")

	# 方向映射：atlas (north/south/east/west) -> Godot (up/down/right/left)
	var direction_map: Dictionary = {
		"north": "up",
		"south": "down",
		"east": "right",
		"west": "left"
	}

	# 直接使用 atlas_config 中的動畫名稱和配置
	for anim_name: String in animations.keys():
		# 找出方向：idle_north -> north, walk_east -> east 等
		var direction: String = ""
		for dir_key: String in direction_map.keys():
			if anim_name.contains(dir_key):
				direction = dir_key
				break

		if direction.is_empty():
			continue

		var anim_info: Dictionary = animations[anim_name]
		var row: int = anim_info.get("row", 0)
		var start: int = anim_info.get("start", 0)
		var end: int = anim_info.get("end", 1)
		var fps: float = anim_info.get("fps", 6.0)
		var loop: bool = anim_info.get("loop", true)

		# 轉換方向名稱（north -> up, south -> down 等）
		var godot_anim_name: String = anim_name.replace(direction, direction_map[direction])

		frames.add_animation(godot_anim_name)
		frames.set_animation_speed(godot_anim_name, fps)
		frames.set_animation_loop(godot_anim_name, loop)

		# 添加每一幀（使用 AtlasTexture）
		for col: int in range(start, end):
			var atlas: AtlasTexture = AtlasTexture.new()
			atlas.atlas = texture
			var x: int = col * frame_size[0]
			var y: int = row * frame_size[1]
			atlas.region = Rect2(x, y, frame_size[0], frame_size[1])
			frames.add_frame(godot_anim_name, atlas)

	print("SpriteSheetLoader: Loaded animations for %s: %s" % [
		character_name,
		", ".join(frames.get_animation_names())
	])
	return frames

## 智能加載：優先預編譯，備選動態生成
## character_dir_path: 角色資料夾路徑
static func smart_load(character_dir_path: String) -> SpriteFrames:
	var character_name: String = character_dir_path.get_file()

	# 優先嘗試預編譯版本
	var precompiled: SpriteFrames = load_precompiled_spritesheet(character_name)
	if precompiled != null:
		print("SpriteSheetLoader: Loaded precompiled spritesheet for %s" % character_name)
		return precompiled

	# 備選：動態生成（開發時或更新時）
	print("SpriteSheetLoader: Precompiled not found, generating from metadata for %s" % character_name)
	return load_from_metadata(character_dir_path)
