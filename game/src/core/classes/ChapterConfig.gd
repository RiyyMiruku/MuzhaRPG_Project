## ChapterConfig — 章節定義資源
## 每個章節對應一個 chapter.tres，宣告章節範圍、出場 NPC、對話差異片段等。
## 建立：在 chapters/<chapter_id>/ 下右鍵 → New Resource → ChapterConfig
class_name ChapterConfig
extends Resource

# ── 識別 ──────────────────────────────────────────────────────────────────
## 唯一 ID，建議格式：ch<NN>_<short_name>，如 "ch01_arrival"
@export var chapter_id: String = ""
## 章節顯示名稱（繁體中文）
@export var display_name: String = ""
## 排序，1 = 第一章
@export var order: int = 0

# ── 進入條件 ───────────────────────────────────────────────────────────────
## 必須先完成的章節 ID 陣列。空 = 隨時可進。
@export var prerequisites: Array[String] = []

# ── 章節範圍 ───────────────────────────────────────────────────────────────
## 本章節會用到的 zone（用於資源預載 / 限制玩家移動）
@export var zones_used: Array[String] = []
## 本章節會出場的 NPC ID 陣列（不在此清單的 NPC 可被隱藏）
@export var npcs_present: Array[String] = []

# ── NPC 對話差異 ──────────────────────────────────────────────────────────
## { npc_id: "章節差異片段，會附加到 NPC 基底 system_prompt 之後" }
## 例：{ "chen_ayi": "（玩家剛來木柵第一天，你不認識他）" }
## AIClient 在組合 prompt 時會注入。
@export var npc_overlays: Dictionary = {}

# ── 章節事件腳本 ──────────────────────────────────────────────────────────
## 章節啟動時執行的腳本（含信號連接、quest 註冊等）。
## 預期 Script 有 register(manager) 與 unregister(manager) 兩個方法。
@export var events_script: Script = null

# ── 任務 ──────────────────────────────────────────────────────────────────
## 本章節包含的 quest 資源（暫用 Resource，待 QuestConfig 類別完成後改型）
@export var quests: Array[Resource] = []

# ── 完成條件 ──────────────────────────────────────────────────────────────
## 必須觸發的 StoryManager flag 名稱集。全部觸發後章節判定完成。
@export var completion_flags: Array[String] = []

# ── 元資料（可選） ────────────────────────────────────────────────────────
## 章節摘要（給開發者看的文字提示）
@export_multiline var synopsis: String = ""


# ── 工具方法 ──────────────────────────────────────────────────────────────
## 取得指定 NPC 在本章的對話差異片段；無則回空字串。
func get_npc_overlay(npc_id: String) -> String:
	return npc_overlays.get(npc_id, "")

## 該 NPC 是否在本章節出場
func includes_npc(npc_id: String) -> bool:
	return npcs_present.is_empty() or npc_id in npcs_present

## 該 zone 是否在本章節範圍內
func includes_zone(zone_id: String) -> bool:
	return zones_used.is_empty() or zone_id in zones_used
