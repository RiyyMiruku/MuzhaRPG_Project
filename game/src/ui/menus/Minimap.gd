## Minimap — 小地圖面板
class_name Minimap
extends Control

const MAP_NODES: Dictionary = {
	"zone_nccu":      Vector2(200, 160),
	"zone_market":    Vector2(80, 160),
	"zone_zhinan":    Vector2(80, 60),
	"zone_riverside": Vector2(320, 160),
}

const MAP_EDGES: Array = [
	["zone_nccu", "zone_market"],
	["zone_nccu", "zone_riverside"],
	["zone_market", "zone_zhinan"],
]

@onready var _map_panel: Panel = $MapPanel

var _map_draw: Control

func _ready() -> void:
	UIManager.register("Minimap", self)
	_map_draw = Control.new()
	_map_draw.set_anchors_preset(PRESET_FULL_RECT)
	_map_panel.add_child(_map_draw)
	_map_draw.draw.connect(_on_draw)

func _input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_map"):
		if UIManager.current_panel == "Minimap":
			UIManager.pop()
		elif not UIManager.is_any_open:
			_map_draw.queue_redraw()
			UIManager.toggle("Minimap")
		get_viewport().set_input_as_handled()

func _on_draw() -> void:
	var current: String = StoryManager.current_zone
	var unlocked: Array[String] = StoryManager.unlocked_zones

	for edge: Array in MAP_EDGES:
		var from_id: String = edge[0]
		var to_id: String = edge[1]
		if MAP_NODES.has(from_id) and MAP_NODES.has(to_id):
			var color: Color = Color(0.4, 0.4, 0.4) if (unlocked.has(from_id) and unlocked.has(to_id)) else Color(0.2, 0.2, 0.2)
			_map_draw.draw_line(MAP_NODES[from_id], MAP_NODES[to_id], color, 2.0)

	for zone_id: String in MAP_NODES:
		var pos: Vector2 = MAP_NODES[zone_id]
		var is_current: bool = zone_id == current
		var is_unlocked: bool = unlocked.has(zone_id)

		var circle_color: Color
		if is_current:
			circle_color = Color(0.3, 1.0, 0.4)
		elif is_unlocked:
			circle_color = Color(0.6, 0.6, 0.8)
		else:
			circle_color = Color(0.3, 0.3, 0.3)
		_map_draw.draw_circle(pos, 12.0 if is_current else 8.0, circle_color)

		var display_name: String = StoryManager.ZONE_DISPLAY.get(zone_id, zone_id)
		if not is_unlocked:
			display_name = "???"
		var font: Font = ThemeDB.fallback_font
		var font_size: int = 11
		var text_size: Vector2 = font.get_string_size(display_name, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
		_map_draw.draw_string(font, pos + Vector2(-text_size.x / 2, 24), display_name, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.WHITE)
