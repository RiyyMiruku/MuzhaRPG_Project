## SpriteSheetLoader — 從 spritesheet PNG 自動建立 SpriteFrames
## 支援 N 列 × M 行的標準格子 spritesheet。
class_name SpriteSheetLoader
extends RefCounted

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
