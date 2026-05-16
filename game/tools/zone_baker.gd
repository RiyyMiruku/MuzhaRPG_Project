@tool
extends Node2D

## Cells to paint into the TileMapDual child. Populated by
## `scripts/build_zone.py` when emitting this zone .tscn — do not edit by hand.
@export var terrain_cells: Array[Vector2i] = []
## Which terrain index inside the TileMapDual's TileSet to paint with.
@export var terrain_id: int = 1
## YAML 來源路徑(repo-relative)。builder 寫入,Lock/Unlock 按鈕用。
## Hybrid zone 會有多個(e.g. pharmacy/1983.yaml + pharmacy/modern.yaml)。
@export var yaml_paths: Array[String] = []

@export_tool_button("Bake terrain") var _bake_action: Callable = _bake_terrain
@export_tool_button("Clear terrain") var _clear_action: Callable = _clear_terrain
@export_tool_button("Lock YAML (frozen: true)") var _lock_action: Callable = _lock_yaml
@export_tool_button("Unlock YAML") var _unlock_action: Callable = _unlock_yaml


func _bake_terrain() -> void:
	var tmd: TileMapLayer = _get_dual()
	if tmd == null:
		push_error("[zone_baker] TileMapDual node not found at $TileMapLayer/TileMapDual")
		return
	if tmd.tile_set == null:
		push_error("[zone_baker] TileMapDual.tile_set is null. Assign a TileSet first.")
		return
	for cell in terrain_cells:
		tmd.call("draw_cell", cell, terrain_id)
	print("[zone_baker] Baked %d cells. Save scene (Ctrl+S) to persist." % terrain_cells.size())


func _clear_terrain() -> void:
	var tmd: TileMapLayer = _get_dual()
	if tmd == null:
		return
	tmd.clear()
	print("[zone_baker] Cleared.")


func _lock_yaml() -> void:
	_set_yaml_frozen(true)


func _unlock_yaml() -> void:
	_set_yaml_frozen(false)


## 把 `frozen: true` 加進或從 YAML 移除(用 regex,適用本專案的簡單 YAML)
func _set_yaml_frozen(target: bool) -> void:
	if yaml_paths.is_empty():
		push_error("[zone_baker] yaml_paths empty — re-run build_zone.py first")
		return
	var repo_root: String = ProjectSettings.globalize_path("res://").path_join("..")
	var processed: int = 0
	for rel: String in yaml_paths:
		var abs_path: String = repo_root.path_join(rel).simplify_path()
		if not FileAccess.file_exists(abs_path):
			push_warning("[zone_baker] YAML not found: %s" % abs_path)
			continue
		var f: FileAccess = FileAccess.open(abs_path, FileAccess.READ)
		if f == null:
			push_warning("[zone_baker] cannot open %s" % abs_path)
			continue
		var text: String = f.get_as_text()
		f.close()

		var new_text: String = _toggle_frozen_line(text, target)
		if new_text == text:
			continue
		var wf: FileAccess = FileAccess.open(abs_path, FileAccess.WRITE)
		if wf == null:
			push_warning("[zone_baker] cannot write %s" % abs_path)
			continue
		wf.store_string(new_text)
		wf.close()
		processed += 1

	var state_word: String = "locked" if target else "unlocked"
	print("[zone_baker] %s %d YAML file(s)." % [state_word, processed])


func _toggle_frozen_line(text: String, target: bool) -> String:
	# 用 regex 找 ^frozen:\s* 開頭的整行
	var re: RegEx = RegEx.new()
	re.compile("(?m)^frozen:\\s*\\w+\\s*$")
	var has_line: bool = re.search(text) != null

	if target:
		if has_line:
			# 已有 → 確保是 true
			return re.sub(text, "frozen: true", false)
		# 沒有 → 在第一個非註解非空行前插入
		var lines: PackedStringArray = text.split("\n")
		var insert_at: int = 0
		for i in range(lines.size()):
			var stripped: String = lines[i].strip_edges()
			if stripped.is_empty() or stripped.begins_with("#"):
				continue
			insert_at = i
			break
		lines.insert(insert_at, "frozen: true")
		return "\n".join(lines)
	else:
		# Unlock — 移除整行
		return re.sub(text, "", false).replace("\n\n\n", "\n\n")


func _get_dual() -> TileMapLayer:
	var node: Node = get_node_or_null("TileMapLayer/TileMapDual")
	if node is TileMapLayer:
		return node
	return null
