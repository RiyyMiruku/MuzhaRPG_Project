## EraManager — 時空切換管理器
##
## Chapter 1 核心 mechanic:同一 zone 內透過 hybrid Era group 切 1983 ↔ modern。
##
## 與 ZoneManager 的分工:
##   - ZoneManager 處理「不同 zone 之間」的場景切換(load 新 .tscn、定位 player)
##   - EraManager 處理「同 zone 內 era 切換」(toggle group visible + tween tint),
##     不換 .tscn,player 位置不動
##
## Hybrid zone 識別:`get_tree().get_nodes_in_group("era_modern")` 不為空就是。
## 單時空 zone(group 不存在)切 era 等於 no-op 視覺上,但 `current_era` 狀態仍會更新。
##
## EraTint mood:
##   1983 → 暖黃 sepia(回憶感) Color(1.0, 0.96, 0.82)
##   modern → 冷藍灰(現實感)   Color(0.78, 0.82, 0.88)
##
## 觸發:玩家對 old_map_paper 互動 → events.gd 呼叫 `EraManager.travel_to("1983")`
extends Node

# ── Signals ─────────────────────────────────────────────────────────────────
signal era_changed(from_era: String, to_era: String)
signal era_transition_started(to_era: String)
signal era_transition_finished(to_era: String)

# ── State ───────────────────────────────────────────────────────────────────
var current_era: String = "modern"

# ── Constants ───────────────────────────────────────────────────────────────
const TINT_PRESETS: Dictionary = {
	"1983":   Color(1.0, 0.96, 0.82),
	"modern": Color(0.78, 0.82, 0.88),
}
const ERA_GROUP_PREFIX: String = "era_"
## 閃光持續時間(配合劇本「燈泡閃了一下」)
const FLASH_DURATION: float = 0.5

# ── Public API ──────────────────────────────────────────────────────────────
func travel_to(target_era: String) -> void:
	if target_era == current_era:
		return
	if not TINT_PRESETS.has(target_era):
		push_error("EraManager: unknown era %s" % target_era)
		return

	var old_era: String = current_era
	era_transition_started.emit(target_era)

	# 1. 找當前 zone 的 EraTint 節點(可能不存在 — 單時空 zone)
	var tint: CanvasModulate = _find_era_tint()

	# 2. 短促閃白 → 切 visibility → 漸到目標 tint(燈泡閃感)
	if tint != null:
		await _flash_and_swap(tint, target_era)
	else:
		_swap_visibility(target_era)

	current_era = target_era
	era_changed.emit(old_era, target_era)
	era_transition_finished.emit(target_era)

## 給新 zone 載入完後手動呼叫:套用當前 era 的可見性 + tint
## (因為 zone .tscn 預設可見的 era 可能跟 current_era 不一致)
func apply_to_current_zone() -> void:
	_swap_visibility(current_era)
	var tint: CanvasModulate = _find_era_tint()
	if tint != null:
		tint.color = TINT_PRESETS[current_era]

# ── Internal ────────────────────────────────────────────────────────────────
func _flash_and_swap(tint: CanvasModulate, target_era: String) -> void:
	var tween: Tween = create_tween()
	# Phase A:tint → 白色(閃光峰值)
	tween.tween_property(tint, "color", Color.WHITE, FLASH_DURATION * 0.25)
	# Phase B:在閃光峰值時切換 visibility(玩家看不見差異)
	tween.tween_callback(_swap_visibility.bind(target_era))
	# Phase C:白色 → 目標 era 的 tint
	tween.tween_property(
		tint, "color", TINT_PRESETS[target_era], FLASH_DURATION * 0.75
	)
	await tween.finished

func _swap_visibility(target_era: String) -> void:
	# 遍歷所有 era_* group,只留 target_era 的可見
	for era_key: String in TINT_PRESETS:
		var group_name: String = ERA_GROUP_PREFIX + era_key
		var nodes: Array[Node] = get_tree().get_nodes_in_group(group_name)
		var visible_flag: bool = (era_key == target_era)
		for n: Node in nodes:
			if n is CanvasItem:
				(n as CanvasItem).visible = visible_flag

func _find_era_tint() -> CanvasModulate:
	# 假設 EraTint 在當前 zone 內名為 "EraTint",透過 group 找最穩
	# 但 builder 沒幫 EraTint 加 group,改用 scene tree 搜尋
	var root: Node = get_tree().current_scene
	if root == null:
		return null
	var found: Node = root.find_child("EraTint", true, false)
	if found is CanvasModulate:
		return found as CanvasModulate
	return null

# ── Serialization(GameManager.save_game 用) ────────────────────────────────
func serialize() -> Dictionary:
	return {"current_era": current_era}

func deserialize(data: Dictionary) -> void:
	current_era = data.get("current_era", "modern")
