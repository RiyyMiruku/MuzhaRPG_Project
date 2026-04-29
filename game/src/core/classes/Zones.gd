## Zones — 區域定義 single source of truth
##
## 集中所有 zone 的：display name / scene path / entry points / 世界地圖位置 /
## 連接關係。ZoneManager / StoryManager / LiveMinimap 都查詢本檔，避免散落同步。
##
## 新增 zone 流程：
##   1. 在 ALL 加一個 entry（含 5 個欄位）
##   2. 在 maps/zones/ 放對應 .tscn
##   3. 在連接的鄰居 zone `connects_to` 加上自己（雙向不會自動補）
##
## 未來 era 擴充（Phase 2 EraManager）：
##   每個 zone 可加 `era_variants: { "1983": "res://...zone_xxx_1983.tscn" }`，
##   `scene_path(id, era)` 會回傳對應變體；不存在則回傳預設 scene。
class_name Zones
extends RefCounted

## 起始區域（新遊戲 / save 預設）
const STARTING: String = "zone_nccu"

## 區域定義表 — single source of truth
const ALL: Dictionary = {
	"zone_nccu": {
		"display": "政大正門",
		"scene": "res://src/maps/zones/zone_nccu.tscn",
		"world_pos": Vector2(250, 200),
		"entry_points": {
			"default": Vector2(0, 50),
			"from_market": Vector2(-200, 0),
			"from_riverside": Vector2(200, 0),
		},
		"connects_to": ["zone_market", "zone_riverside"],
	},
	"zone_market": {
		"display": "木柵市場",
		"scene": "res://src/maps/zones/zone_market.tscn",
		"world_pos": Vector2(100, 200),
		"entry_points": {
			"default": Vector2(0, 50),
			"from_nccu": Vector2(200, 0),
			"from_zhinan": Vector2(0, -100),
		},
		"connects_to": ["zone_nccu", "zone_zhinan"],
	},
	"zone_zhinan": {
		"display": "指南宮",
		"scene": "res://src/maps/zones/zone_zhinan.tscn",
		"world_pos": Vector2(100, 80),
		"entry_points": {
			"default": Vector2(0, 50),
			"from_market": Vector2(0, 100),
		},
		"connects_to": ["zone_market"],
	},
	"zone_riverside": {
		"display": "道南河濱公園",
		"scene": "res://src/maps/zones/zone_riverside.tscn",
		"world_pos": Vector2(400, 200),
		"entry_points": {
			"default": Vector2(0, 50),
			"from_nccu": Vector2(0, -100),
		},
		"connects_to": ["zone_nccu"],
	},
}

# ── Query API ───────────────────────────────────────────────────────────────
static func has_zone(zone_id: String) -> bool:
	return ALL.has(zone_id)

static func all_ids() -> Array:
	return ALL.keys()

static func display_name(zone_id: String) -> String:
	return ALL.get(zone_id, {}).get("display", zone_id)

## 取場景路徑。預留 era 參數，目前未使用；Phase 2 擴 era_variants 時生效。
static func scene_path(zone_id: String, _era: String = "") -> String:
	var data: Dictionary = ALL.get(zone_id, {})
	# Phase 2 hook: if data has "era_variants" and _era 非空 → 優先取變體
	# var variants: Dictionary = data.get("era_variants", {})
	# if not _era.is_empty() and variants.has(_era):
	#     return variants[_era]
	return data.get("scene", "")

## 取入口座標。entry_point 不存在會 fallback 到 "default"，再不存在回 Vector2.ZERO。
static func entry_position(zone_id: String, entry_point: String = "default") -> Vector2:
	var entries: Dictionary = ALL.get(zone_id, {}).get("entry_points", {})
	if entries.has(entry_point):
		return entries[entry_point]
	return entries.get("default", Vector2.ZERO)

static func world_position(zone_id: String) -> Vector2:
	return ALL.get(zone_id, {}).get("world_pos", Vector2.ZERO)

## 衍生世界地圖邊（去重雙向）— 給 LiveMinimap 畫線
static func all_edges() -> Array:
	var edges: Array = []
	var seen: Dictionary = {}
	for zone_id: String in ALL:
		for neighbor: String in ALL[zone_id].get("connects_to", []):
			var a: String = zone_id if zone_id < neighbor else neighbor
			var b: String = neighbor if zone_id < neighbor else zone_id
			var key: String = "%s|%s" % [a, b]
			if not seen.has(key):
				seen[key] = true
				edges.append([a, b])
	return edges
