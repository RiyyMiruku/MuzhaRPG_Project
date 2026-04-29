## StoryBeat — 預寫對話節拍 resource
##
## 一個 beat = 一段必須一字不差出現的劇情對話（含可選 choices）。
## BeatRunner 在玩家互動 NPC 時優先檢查是否有 active beat；有則跑 beat 而非 AI。
##
## 命名建議：beat_id = "chXX_<short_name>"，檔名同 beat_id.tres。
class_name StoryBeat
extends Resource

## 唯一 ID（建議 chXX_<short_name>）
@export var beat_id: String = ""

# ── 觸發條件（全部成立才會啟用） ──────────────────────────────────────────
## 必須全部 true 的 flags（key -> true）
@export var trigger_flags: Dictionary = {}
## 必須已 record 的 event ID（任一）
@export var trigger_event: String = ""
## 玩家跟此 NPC 互動時觸發
@export var trigger_npc_id: String = ""
## 進入此 zone 觸發（無 NPC 互動，純走進去就跑）
@export var trigger_zone: String = ""

# ── 對話內容 ─────────────────────────────────────────────────────────────
## 依序播放的對話列。每條格式：{ "speaker": "name|narrator", "text": "..." }
@export var dialogue_lines: Array = []

## 最後選擇（可選，沒有就直接結束）
## 每項格式：{ "text": "選項文字", "set_flags": {"key": true} }
@export var choices: Array = []

# ── 完成後副作用 ──────────────────────────────────────────────────────────
@export var on_complete_flags: Dictionary = {}
@export var on_complete_event: String = ""

## 是否阻擋玩家移動（cutscene mode）
@export var blocks_input: bool = true


# ── 觸發判定 ──────────────────────────────────────────────────────────────
## 給定當前狀態，判斷此 beat 是否該啟用
func is_triggered_for(npc_id: String, flags: Dictionary, completed_events: Array, current_zone: String) -> bool:
	# NPC 互動觸發
	if not trigger_npc_id.is_empty() and trigger_npc_id != npc_id:
		return false
	# Zone 觸發（npc_id 為空時才檢查）
	if not trigger_zone.is_empty() and npc_id.is_empty():
		if trigger_zone != current_zone:
			return false
	# Event 觸發
	if not trigger_event.is_empty() and not completed_events.has(trigger_event):
		return false
	# Flags 必須全部 match
	for key: String in trigger_flags:
		if flags.get(key, null) != trigger_flags[key]:
			return false
	return true
