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
## chapter 1 故事起點:阿謙在老公寓醒來,走出去到木柵市場現代版,打開藥行鐵門
const STARTING: String = "zone_apartment_muzha"

## 區域定義表 — single source of truth
##
## 章節 1 拓樸(hybrid era):
##   apartment_muzha ↔ market ↔ {pharmacy, law_office}
##   pharmacy ↔ pharmacy_backyard
##
## Era 機制:
##   zone_pharmacy 與 zone_market 是 hybrid 場景(同一 .tscn 內含 1983 / modern
##   兩套節點,以 group `era_1983` / `era_modern` 標記)。
##   EraManager(autoload,未實作)透過 `get_tree().get_nodes_in_group("era_<era>")`
##   切換 visible + tween EraTint CanvasModulate.color。
##   ZoneManager 不參與 era 切換 — era 切換不離開 zone,是 in-place toggle。
##
##   單時空 zone(backyard / apartment / law_office) 沒 era group,
##   無論當前 era 都長一樣。
const ALL: Dictionary = {
	"zone_apartment_muzha": {
		"display": "木柵老公寓",
		"scene": "res://src/maps/zones/zone_apartment_muzha.tscn",
		"world_pos": Vector2(300, 100),
		"entry_points": {
			"default": Vector2(-96, 48),
			"from_market": Vector2(-96, 48),
		},
		"connects_to": ["zone_market"],
	},
	"zone_market": {
		"display": "木柵市場",
		"scene": "res://src/maps/zones/zone_market.tscn",
		"world_pos": Vector2(200, 250),
		"entry_points": {
			"default": Vector2(-144, 72),
			"from_apartment": Vector2(-144, 72),
			"from_pharmacy": Vector2(0, -80),
			"from_law_office": Vector2(150, 0),
		},
		"connects_to": ["zone_apartment_muzha", "zone_pharmacy", "zone_law_office"],
	},
	"zone_pharmacy": {
		"display": "榮昌中藥行",
		"scene": "res://src/maps/zones/zone_pharmacy.tscn",
		"world_pos": Vector2(180, 200),
		"entry_points": {
			"default": Vector2(-128, 64),
			"from_market": Vector2(-128, 64),
			"from_backyard": Vector2(150, 0),
		},
		"connects_to": ["zone_market", "zone_pharmacy_backyard"],
	},
	"zone_pharmacy_backyard": {
		"display": "榮昌中藥行後院",
		"scene": "res://src/maps/zones/zone_pharmacy_backyard.tscn",
		"world_pos": Vector2(180, 150),
		"entry_points": {
			"default": Vector2(-160, -80),
			"from_pharmacy": Vector2(-160, -80),
		},
		"connects_to": ["zone_pharmacy"],
	},
	"zone_law_office": {
		"display": "律師事務所",
		"scene": "res://src/maps/zones/zone_law_office.tscn",
		"world_pos": Vector2(400, 250),
		"entry_points": {
			"default": Vector2(-96, 48),
			"from_market": Vector2(-96, 48),
		},
		"connects_to": ["zone_market"],
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
