@tool
extends Node2D

const TEST_CELLS: Array[Vector2i] = [
	Vector2i(0, 0),
	Vector2i(1, 0),
	Vector2i(2, 0),
	Vector2i(1, 1),
	Vector2i(1, -1),
]

@export_tool_button("Bake 5 cells (grass)") var _bake_action: Callable = _bake_cells
@export_tool_button("Clear all cells") var _clear_action: Callable = _clear_cells


func _bake_cells() -> void:
	var tmd: TileMapLayer = _get_dual()
	if tmd == null:
		push_error("[zone_baker_test] TileMapDual node not found under $TileMapLayer/TileMapDual")
		return
	for cell in TEST_CELLS:
		tmd.call("draw_cell", cell, 1)
	print("[zone_baker_test] Baked %d cells. Save scene (Ctrl+S) and inspect tile_map_data." % TEST_CELLS.size())


func _clear_cells() -> void:
	var tmd: TileMapLayer = _get_dual()
	if tmd == null:
		return
	tmd.clear()
	print("[zone_baker_test] Cleared all cells.")


func _get_dual() -> TileMapLayer:
	var node: Node = get_node_or_null("TileMapLayer/TileMapDual")
	if node is TileMapLayer:
		return node
	return null
