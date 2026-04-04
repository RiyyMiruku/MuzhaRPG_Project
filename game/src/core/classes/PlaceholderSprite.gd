## PlaceholderSprite — 程式化產生佔位精靈工具
## 當 AnimatedSprite2D 沒有 SpriteFrames 時，自動產生彩色方塊作為替代。
## 之後換上真正的像素美術時，只要在編輯器中設定 SpriteFrames 即可，此腳本會自動跳過。
class_name PlaceholderSprite
extends RefCounted

## 為 AnimatedSprite2D 產生佔位用的 SpriteFrames。
## body_color: 角色身體顏色
## accent_color: 方向指示色（用來區分正面/背面）
## size: 角色尺寸（像素）
static func generate_sprite_frames(
	body_color: Color = Color.CORNFLOWER_BLUE,
	accent_color: Color = Color.WHITE,
	size: Vector2i = Vector2i(16, 24)
) -> SpriteFrames:
	var frames: SpriteFrames = SpriteFrames.new()

	# 移除預設的 "default" 動畫
	if frames.has_animation("default"):
		frames.remove_animation("default")

	# 建立 8 個動畫：idle/walk × 4 方向
	var directions: Array[String] = ["_down", "_up", "_left", "_right"]
	for dir in directions:
		frames.add_animation("idle" + dir)
		frames.set_animation_speed("idle" + dir, 4)
		frames.set_animation_loop("idle" + dir, true)

		frames.add_animation("walk" + dir)
		frames.set_animation_speed("walk" + dir, 8)
		frames.set_animation_loop("walk" + dir, true)

	# 為每個動畫產生幀
	for dir in directions:
		# idle: 1 幀靜止
		var idle_tex: Texture2D = _create_frame(body_color, accent_color, size, dir, false)
		frames.add_frame("idle" + dir, idle_tex)

		# walk: 2 幀交替（簡易走路動畫）
		var walk_tex1: Texture2D = _create_frame(body_color, accent_color, size, dir, false)
		var walk_tex2: Texture2D = _create_frame(body_color, accent_color, size, dir, true)
		frames.add_frame("walk" + dir, walk_tex1)
		frames.add_frame("walk" + dir, walk_tex2)

	return frames

## 產生單一幀的 ImageTexture
static func _create_frame(
	body_color: Color,
	accent_color: Color,
	size: Vector2i,
	direction: String,
	alt_frame: bool
) -> ImageTexture:
	var img: Image = Image.create(size.x, size.y, false, Image.FORMAT_RGBA8)

	# 填充身體（主色）
	img.fill(Color.TRANSPARENT)
	var body_rect: Rect2i = Rect2i(2, 4, size.x - 4, size.y - 4)
	if alt_frame:
		# 走路第二幀：身體微微偏移 1px
		body_rect = Rect2i(2, 3, size.x - 4, size.y - 4)
	_fill_rect(img, body_rect, body_color)

	# 畫頭部（上方較亮的區塊）
	var head_rect: Rect2i = Rect2i(4, 2, size.x - 8, 6)
	if alt_frame:
		head_rect = Rect2i(4, 1, size.x - 8, 6)
	_fill_rect(img, head_rect, body_color.lightened(0.3))

	# 方向指示（不同方向在不同位置畫一個小標記）
	var marker_size: int = 3
	var mx: int = 0
	var my: int = 0
	match direction:
		"_down":
			mx = size.x / 2 - 1
			my = size.y - 6
		"_up":
			mx = size.x / 2 - 1
			my = 2
		"_left":
			mx = 2
			my = size.y / 2 - 1
		"_right":
			mx = size.x - marker_size - 2
			my = size.y / 2 - 1
	_fill_rect(img, Rect2i(mx, my, marker_size, marker_size), accent_color)

	# 畫簡易眼睛（僅正面 _down）
	if direction == "_down":
		_fill_rect(img, Rect2i(5, 4, 2, 2), Color.WHITE)
		_fill_rect(img, Rect2i(size.x - 7, 4, 2, 2), Color.WHITE)

	var tex: ImageTexture = ImageTexture.create_from_image(img)
	return tex

## 在 Image 上填充一個矩形區域
static func _fill_rect(img: Image, rect: Rect2i, color: Color) -> void:
	for x in range(max(0, rect.position.x), min(img.get_width(), rect.position.x + rect.size.x)):
		for y in range(max(0, rect.position.y), min(img.get_height(), rect.position.y + rect.size.y)):
			img.set_pixel(x, y, color)
