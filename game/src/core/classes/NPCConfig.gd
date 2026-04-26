## NPCConfig — NPC 設定資源
## 每個 NPC 對應一個 .tres 資源檔，儲存人設與 AI 參數。
## 建立方式：在 Godot 編輯器中右鍵 → New Resource → 選擇 NPCConfig
class_name NPCConfig
extends Resource

# ── 識別 ──────────────────────────────────────────────────────────────────
## 唯一識別碼，貫穿整個系統 — 同時是：
##   - art_source/characters/<id>/ 資料夾名
##   - spritesheet_cache/<id>.png 檔名 + atlas_config 的 key
##   - assets/textures/portraits/<id>.png 立繪檔名
##   - .tres 檔名（建議）
@export var npc_id: String = ""
@export var display_name: String = ""            # 顯示名稱（繁體中文），如 "陳阿姨"
@export var display_name_en: String = ""         # 英文名稱（可選）

# ── 世界資訊 ───────────────────────────────────────────────────────────────
@export var location_zone: String = ""           # 所屬區域，如 "zone_market"

# ── AI 人設 ────────────────────────────────────────────────────────────────
## 系統提示詞（繁體中文）。定義 NPC 的個性、說話方式、背景知識。
## AIClient 會在此之後自動附加動態情境資訊。
@export_multiline var system_prompt: String = ""
@export var personality_tags: Array[String] = [] # 如 ["親切", "碎念", "在地知識"]

# ── AI 推論參數 ────────────────────────────────────────────────────────────
## temperature: 越高越有創意，越低越穩定。NPC 個性越跳脫可設越高。
@export_range(0.0, 2.0, 0.05) var base_temperature: float = 0.7
## max_response_tokens: 限制 AI 一次回應的長度。
@export_range(50, 500, 10) var max_response_tokens: int = 200
## conversation_memory_turns: 保留多少輪對話歷史傳給 AI（每輪 = 玩家+NPC 各一條）。
@export_range(2, 20, 2) var conversation_memory_turns: int = 6

# ── 關係系統 (Phase 3) ────────────────────────────────────────────────────
## 初始好感度（-100 到 100）。0 = 陌生人。
@export_range(-100, 100, 5) var initial_relationship: int = 0


# ── 自動推導路徑（不用手填）────────────────────────────────────────────────
## 載入對話立繪。檔案位於 res://assets/textures/portraits/<npc_id>.png
func get_portrait() -> Texture2D:
	var path: String = "res://assets/textures/portraits/%s.png" % npc_id
	if not ResourceLoader.exists(path):
		push_warning("NPCConfig: Portrait not found for '%s'" % npc_id)
		return null
	return load(path)
