## LiveMinimap — 三層地圖系統
## 層級 0: HUD 右下角小地圖（即時追蹤，始終顯示）
## 層級 1: 放大版區域地圖（按 M 開啟，顯示 NPC/轉場點詳細資訊）
## 層級 2: 世界地圖（在層級 1 點擊切換，顯示區域連接關係）
class_name LiveMinimap
extends Control

enum MapLayer { HUD, ZONE_DETAIL, WORLD }
var _current_layer: MapLayer = MapLayer.HUD

@export var world_range: float = 300.0
@export var map_size: float = 108.0

const EXPANDED_SIZE: Vector2 = Vector2(500, 360)

const WORLD_NODES: Dictionary = {
	"zone_nccu":      Vector2(250, 200),
	"zone_market":    Vector2(100, 200),
	"zone_zhinan":    Vector2(100, 80),
	"zone_riverside": Vector2(400, 200),
}
const WORLD_EDGES: Array = [
	["zone_nccu", "zone_market"],
	["zone_nccu", "zone_riverside"],
	["zone_market", "zone_zhinan"],
]

const COLOR_BG: Color = Color(0.08, 0.1, 0.12, 0.85)
const COLOR_BORDER: Color = Color(0.4, 0.4, 0.4, 0.6)
const COLOR_PLAYER: Color = Color(0.3, 0.8, 1.0)
const COLOR_NPC: Color = Color(1.0, 0.6, 0.2)
const COLOR_TRANSITION: Color = Color(0.4, 1.0, 0.5, 0.8)
const COLOR_ZONE_CURRENT: Color = Color(0.3, 1.0, 0.4)
const COLOR_ZONE_UNLOCKED: Color = Color(0.6, 0.6, 0.8)
const COLOR_ZONE_LOCKED: Color = Color(0.3, 0.3, 0.3)

# 記住 HUD 位置用於恢復
var _hud_offset_left: float
var _hud_offset_top: float
var _hud_offset_right: float
var _hud_offset_bottom: float

func _ready() -> void:
	# 記住初始 offset（HUD 模式定位）
	await get_tree().process_frame
	_hud_offset_left = offset_left
	_hud_offset_top = offset_top
	_hud_offset_right = offset_right
	_hud_offset_bottom = offset_bottom

func _process(_delta: float) -> void:
	if visible:
		queue_redraw()

func _draw() -> void:
	match _current_layer:
		MapLayer.HUD:
			_draw_hud_minimap()
		MapLayer.ZONE_DETAIL:
			_draw_zone_detail()
		MapLayer.WORLD:
			_draw_world_map()

func _input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_map"):
		if _current_layer == MapLayer.HUD:
			if not UIManager.is_any_open:
				_expand()
		else:
			_collapse()
		get_viewport().set_input_as_handled()
		return

	# 放大模式下的操作
	if _current_layer != MapLayer.HUD:
		# ESC 也能關閉地圖
		if event.is_action_pressed("pause"):
			_collapse()
			get_viewport().set_input_as_handled()
			return
		# 滑鼠點擊
		if event is InputEventMouseButton:
			var mb: InputEventMouseButton = event as InputEventMouseButton
			if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
				_handle_click(mb.global_position)
		get_viewport().set_input_as_handled()

# ── 展開 / 收合 ─────────────────────────────────────────────────────────────
func _expand() -> void:
	_current_layer = MapLayer.ZONE_DETAIL
	# 改為螢幕置中
	anchor_left = 0.5
	anchor_top = 0.5
	anchor_right = 0.5
	anchor_bottom = 0.5
	offset_left = -EXPANDED_SIZE.x / 2
	offset_top = -EXPANDED_SIZE.y / 2
	offset_right = EXPANDED_SIZE.x / 2
	offset_bottom = EXPANDED_SIZE.y / 2
	# 通知 UIManager 暫停遊戲 + 攔截輸入
	UIManager.register("MapExpanded", self)
	UIManager.push("MapExpanded")

func _collapse() -> void:
	_current_layer = MapLayer.HUD
	# 恢復右下角定位
	anchor_left = 1.0
	anchor_top = 1.0
	anchor_right = 1.0
	anchor_bottom = 1.0
	offset_left = _hud_offset_left
	offset_top = _hud_offset_top
	offset_right = _hud_offset_right
	offset_bottom = _hud_offset_bottom
	# 恢復遊戲（不讓 UIManager hide 我們，因為 HUD 小地圖要繼續顯示）
	UIManager.pop_all()

func _handle_click(global_click: Vector2) -> void:
	var local: Vector2 = global_click - global_position
	# 切換按鈕區域（右上角）
	var btn_rect: Rect2 = Rect2(EXPANDED_SIZE.x - 110, 8, 100, 24)
	if btn_rect.has_point(local):
		if _current_layer == MapLayer.ZONE_DETAIL:
			_current_layer = MapLayer.WORLD
		else:
			_current_layer = MapLayer.ZONE_DETAIL
		queue_redraw()

# ══════════════════════════════════════════════════════════════════════════════
# 層級 0: HUD 小地圖
# ══════════════════════════════════════════════════════════════════════════════
func _draw_hud_minimap() -> void:
	var s: float = map_size
	var center: Vector2 = Vector2(s / 2 + 4, s / 2 + 20)
	var half: float = s / 2
	var sf: float = half / world_range
	var font: Font = ThemeDB.fallback_font

	draw_rect(Rect2(2, 16, s + 4, s + 4), COLOR_BG)
	draw_rect(Rect2(2, 16, s + 4, s + 4), COLOR_BORDER, false, 1.0)

	var zone_name: String = StoryManager.ZONE_DISPLAY.get(StoryManager.current_zone, "")
	draw_string(font, Vector2(4, 14), zone_name, HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.7, 0.7, 0.7, 0.8))
	draw_string(font, Vector2(s - 14, 14), "[M]", HORIZONTAL_ALIGNMENT_LEFT, -1, 8, Color(0.5, 0.5, 0.5, 0.6))

	var player: Player = _find_player()
	if player == null:
		return
	_draw_entities(center, half, sf, player.global_position, font, false)
	_draw_player_icon(center, player)

# ══════════════════════════════════════════════════════════════════════════════
# 層級 1: 放大區域地圖
# ══════════════════════════════════════════════════════════════════════════════
func _draw_zone_detail() -> void:
	var ps: Vector2 = EXPANDED_SIZE
	var center: Vector2 = Vector2(ps.x / 2, ps.y / 2 + 10)
	var half: float = min(ps.x, ps.y) / 2 - 30
	var sf: float = half / (world_range * 1.5)
	var font: Font = ThemeDB.fallback_font

	draw_rect(Rect2(Vector2.ZERO, ps), COLOR_BG)
	draw_rect(Rect2(Vector2.ZERO, ps), COLOR_BORDER, false, 2.0)

	var zone_name: String = StoryManager.ZONE_DISPLAY.get(StoryManager.current_zone, "")
	draw_string(font, Vector2(12, 22), zone_name + " - Zone Map", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color.WHITE)

	# 切換按鈕
	_draw_switch_button(ps, font, "World Map >>")

	draw_arc(center, half, 0, TAU, 64, Color(0.3, 0.3, 0.3, 0.3), 1.0)

	var player: Player = _find_player()
	if player == null:
		return
	_draw_entities(center, half, sf, player.global_position, font, true)
	_draw_player_icon(center, player)

	draw_string(font, Vector2(12, ps.y - 8), "[M] Close", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.5, 0.5, 0.5, 0.7))

# ══════════════════════════════════════════════════════════════════════════════
# 層級 2: 世界地圖
# ══════════════════════════════════════════════════════════════════════════════
func _draw_world_map() -> void:
	var ps: Vector2 = EXPANDED_SIZE
	var font: Font = ThemeDB.fallback_font
	var current: String = StoryManager.current_zone
	var unlocked: Array[String] = StoryManager.unlocked_zones

	draw_rect(Rect2(Vector2.ZERO, ps), COLOR_BG)
	draw_rect(Rect2(Vector2.ZERO, ps), COLOR_BORDER, false, 2.0)
	draw_string(font, Vector2(12, 22), "World Map", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color.WHITE)

	_draw_switch_button(ps, font, "<< Zone Map")

	# 連接線
	for edge: Array in WORLD_EDGES:
		var f: String = edge[0]
		var t: String = edge[1]
		if WORLD_NODES.has(f) and WORLD_NODES.has(t):
			var c: Color = Color(0.5, 0.5, 0.5) if (unlocked.has(f) and unlocked.has(t)) else Color(0.2, 0.2, 0.2)
			draw_line(WORLD_NODES[f], WORLD_NODES[t], c, 2.0)

	# 區域節點
	for zone_id: String in WORLD_NODES:
		var pos: Vector2 = WORLD_NODES[zone_id]
		var is_cur: bool = zone_id == current
		var is_unlk: bool = unlocked.has(zone_id)
		var nc: Color = COLOR_ZONE_CURRENT if is_cur else (COLOR_ZONE_UNLOCKED if is_unlk else COLOR_ZONE_LOCKED)

		draw_circle(pos, 18.0 if is_cur else 14.0, nc * 0.3)
		draw_circle(pos, 16.0 if is_cur else 12.0, nc)

		var dn: String = StoryManager.ZONE_DISPLAY.get(zone_id, zone_id) if is_unlk else "???"
		var ts: Vector2 = font.get_string_size(dn, HORIZONTAL_ALIGNMENT_LEFT, -1, 13)
		draw_string(font, pos + Vector2(-ts.x / 2, 32), dn, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color.WHITE)

		if is_cur:
			draw_string(font, pos + Vector2(-10, -24), "YOU", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, COLOR_PLAYER)

	# 圖例
	var ly: float = ps.y - 36
	draw_circle(Vector2(20, ly), 4, COLOR_ZONE_CURRENT)
	draw_string(font, Vector2(30, ly + 4), "Current", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.6, 0.6, 0.6))
	draw_circle(Vector2(110, ly), 4, COLOR_ZONE_UNLOCKED)
	draw_string(font, Vector2(120, ly + 4), "Explored", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.6, 0.6, 0.6))
	draw_circle(Vector2(200, ly), 4, COLOR_ZONE_LOCKED)
	draw_string(font, Vector2(210, ly + 4), "Locked", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.6, 0.6, 0.6))

	draw_string(font, Vector2(12, ps.y - 8), "[M] Close    Click to switch view", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.5, 0.5, 0.5, 0.7))

# ══════════════════════════════════════════════════════════════════════════════
# 共用繪製
# ══════════════════════════════════════════════════════════════════════════════
func _draw_switch_button(panel_size: Vector2, font: Font, label: String) -> void:
	var r: Rect2 = Rect2(panel_size.x - 110, 8, 100, 24)
	draw_rect(r, Color(0.3, 0.3, 0.4, 0.8))
	draw_rect(r, COLOR_BORDER, false, 1.0)
	draw_string(font, Vector2(panel_size.x - 105, 25), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.8, 0.8, 1.0))

func _draw_entities(center: Vector2, half: float, sf: float, player_pos: Vector2, font: Font, labels: bool) -> void:
	for t: Node in _find_nodes_of_type("ZoneTransitionArea"):
		var ta: ZoneTransitionArea = t as ZoneTransitionArea
		if ta == null:
			continue
		var dp: Vector2 = center + (ta.global_position - player_pos) * sf
		if not _in_bounds(dp, half, center):
			continue
		var diamond: PackedVector2Array = PackedVector2Array([
			dp + Vector2(0, -5), dp + Vector2(5, 0), dp + Vector2(0, 5), dp + Vector2(-5, 0)])
		draw_colored_polygon(diamond, COLOR_TRANSITION)
		var tn: String = StoryManager.ZONE_DISPLAY.get(ta.target_zone, "?")
		if labels:
			draw_string(font, dp + Vector2(-20, -8), "→ " + tn, HORIZONTAL_ALIGNMENT_LEFT, -1, 9, COLOR_TRANSITION)
		else:
			draw_string(font, dp + Vector2(-6, -6), tn.substr(0, 2) if tn.length() > 2 else tn, HORIZONTAL_ALIGNMENT_LEFT, -1, 7, Color(0.4, 1.0, 0.5, 0.5))

	for n: Node in _find_nodes_of_type("BaseNPC"):
		var npc: BaseNPC = n as BaseNPC
		if npc == null or npc.npc_config == null:
			continue
		var dp: Vector2 = center + (npc.global_position - player_pos) * sf
		if not _in_bounds(dp, half, center):
			continue
		draw_circle(dp, 4.0 if labels else 3.0, COLOR_NPC)
		if labels:
			draw_string(font, dp + Vector2(8, 4), npc.npc_config.display_name, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, COLOR_NPC)
		else:
			draw_string(font, dp + Vector2(-3, -5), npc.npc_config.display_name.substr(0, 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 7, COLOR_NPC)

func _draw_player_icon(center: Vector2, player: Player) -> void:
	draw_circle(center, 4.0, COLOR_PLAYER)
	var d: Vector2
	match player.facing:
		BaseCharacter.FacingDirection.UP:    d = Vector2(0, -8)
		BaseCharacter.FacingDirection.DOWN:  d = Vector2(0, 8)
		BaseCharacter.FacingDirection.LEFT:  d = Vector2(-8, 0)
		BaseCharacter.FacingDirection.RIGHT: d = Vector2(8, 0)
	draw_colored_polygon(PackedVector2Array([center + d, center + d.rotated(2.5) * 0.4, center + d.rotated(-2.5) * 0.4]), COLOR_PLAYER)

func _in_bounds(pos: Vector2, half: float, center: Vector2) -> bool:
	return abs(pos.x - center.x) <= half and abs(pos.y - center.y) <= half

func _find_player() -> Player:
	var p: Array[Node] = get_tree().get_nodes_in_group("player")
	return p[0] as Player if not p.is_empty() else null

func _find_nodes_of_type(type_name: String) -> Array[Node]:
	var result: Array[Node] = []
	var zc: Node = get_tree().current_scene.find_child("ZoneContainer", false, false)
	if zc:
		_collect(zc, type_name, result)
	return result

func _collect(node: Node, type_name: String, result: Array[Node]) -> void:
	if (type_name == "BaseNPC" and node is BaseNPC) or (type_name == "ZoneTransitionArea" and node is ZoneTransitionArea):
		result.append(node)
	for c: Node in node.get_children():
		_collect(c, type_name, result)
