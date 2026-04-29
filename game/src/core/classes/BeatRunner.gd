## BeatRunner — 預寫對話節拍 dispatcher
##
## 職責：
##   1. 掃描章節 beats/ 註冊到 registry
##   2. 提供 find_active_beat(npc_id) 給 BaseNPC 互動時查詢
##   3. 跑 beat：依序餵 lines 給 DialogueUI、處理 choices、設 flags、emit event
##
## 不是 autoload — ChapterManager 在 _ready 把 BeatRunner 加為 child，並暴露：
##   ChapterManager.find_active_beat(npc_id) -> StoryBeat
##   ChapterManager.run_beat(beat) -> void
##
## 這樣避免 autoload sprawl，beat 邏輯與章節範疇一致。
class_name BeatRunner
extends Node

signal beat_started(beat_id: String)
signal beat_finished(beat_id: String)

## 已掃到的所有 beats（beat_id -> StoryBeat）
var _beats: Dictionary = {}

## 當前正在跑的 beat
var _active_beat: StoryBeat = null

## 用於餵 lines 的索引
var _line_index: int = 0

## 當前 beat 對應的 DialogueUI（避免 signal bind 後 disconnect 失敗）
var _ui: DialogueUI = null

## ── Public API ──────────────────────────────────────────────────────────
## 從指定資料夾掃描所有 .tres 註冊為 beats
func scan_dir(path: String) -> int:
	var count: int = 0
	if not DirAccess.dir_exists_absolute(path):
		return 0
	var dir: DirAccess = DirAccess.open(path)
	if dir == null:
		return 0
	dir.list_dir_begin()
	var entry: String = dir.get_next()
	while entry != "":
		if entry.ends_with(".tres"):
			var res: Resource = load(path + "/" + entry)
			if res is StoryBeat and not (res as StoryBeat).beat_id.is_empty():
				var beat: StoryBeat = res as StoryBeat
				if StoryManager.completed_events.has("beat_done_" + beat.beat_id):
					pass   # 已完成過的 beat 不重觸發，但仍註冊（測試用）
				_beats[beat.beat_id] = beat
				count += 1
		entry = dir.get_next()
	dir.list_dir_end()
	return count

func clear() -> void:
	_beats.clear()

## 找出目前可觸發的 beat（給定 NPC + 當前狀態）。回傳 null 表示沒有 active beat → 走 AI mode。
func find_active_beat(npc_id: String) -> StoryBeat:
	for beat: StoryBeat in _beats.values():
		# 已完成過 → 跳過
		if StoryManager.completed_events.has("beat_done_" + beat.beat_id):
			continue
		if beat.is_triggered_for(
			npc_id,
			StoryManager.player_flags,
			StoryManager.completed_events,
			StoryManager.current_zone
		):
			return beat
	return null

## 跑指定 beat。需要 DialogueUI 引用。完成後會 emit beat_finished。
func run(beat: StoryBeat, dialogue_ui: DialogueUI) -> void:
	if _active_beat != null:
		push_warning("BeatRunner: already running '%s', ignoring '%s'" % [
			_active_beat.beat_id, beat.beat_id
		])
		return
	_active_beat = beat
	_line_index = 0
	_ui = dialogue_ui
	print("BeatRunner: starting beat '%s' (%d lines, %d choices)" % [
		beat.beat_id, beat.dialogue_lines.size(), beat.choices.size()
	])
	beat_started.emit(beat.beat_id)
	dialogue_ui.open_beat_mode(beat)
	if not dialogue_ui.beat_advance_requested.is_connected(_on_advance):
		dialogue_ui.beat_advance_requested.connect(_on_advance)
	if not dialogue_ui.beat_choice_made.is_connected(_on_choice_made):
		dialogue_ui.beat_choice_made.connect(_on_choice_made)
	# 玩家 ESC 中止 → 視為取消 beat（不寫 on_complete_flags）
	if not dialogue_ui.dialogue_closed.is_connected(_on_dialogue_closed_external):
		dialogue_ui.dialogue_closed.connect(_on_dialogue_closed_external, CONNECT_ONE_SHOT)

func is_active() -> bool:
	return _active_beat != null

## ── Internal ────────────────────────────────────────────────────────────
func _on_advance() -> void:
	if _active_beat == null or _ui == null:
		return
	_line_index += 1
	if _line_index < _active_beat.dialogue_lines.size():
		_ui.show_beat_line(_active_beat.dialogue_lines[_line_index])
	else:
		if _active_beat.choices.is_empty():
			_finish({})
		else:
			_ui.show_choices(_active_beat.choices)

func _on_choice_made(choice_index: int) -> void:
	if _active_beat == null:
		return
	if choice_index < 0 or choice_index >= _active_beat.choices.size():
		push_warning("BeatRunner: invalid choice index %d" % choice_index)
		return
	var choice: Dictionary = _active_beat.choices[choice_index]
	_finish(choice.get("set_flags", {}))

## 玩家 ESC 中止 beat（外部關閉 dialogue 視為取消）— 不寫 on_complete_flags、不標記完成
func _on_dialogue_closed_external() -> void:
	if _active_beat == null:
		return
	# 解除自己的 signal（dialogue_closed 已是 ONE_SHOT 不用斷）
	if _ui:
		if _ui.beat_advance_requested.is_connected(_on_advance):
			_ui.beat_advance_requested.disconnect(_on_advance)
		if _ui.beat_choice_made.is_connected(_on_choice_made):
			_ui.beat_choice_made.disconnect(_on_choice_made)
	var beat_id: String = _active_beat.beat_id
	_active_beat = null
	_line_index = 0
	_ui = null
	beat_finished.emit(beat_id)
	push_warning("BeatRunner: beat '%s' cancelled by ESC" % beat_id)

func _finish(choice_flags: Dictionary) -> void:
	var beat: StoryBeat = _active_beat
	var ui: DialogueUI = _ui
	# 設 choice flags + on_complete_flags
	for key: String in choice_flags:
		StoryManager.set_flag(key, choice_flags[key])
	for key: String in beat.on_complete_flags:
		StoryManager.set_flag(key, beat.on_complete_flags[key])
	# 標記已完成（防重觸發）
	StoryManager.record_event("beat_done_" + beat.beat_id)
	if not beat.on_complete_event.is_empty():
		StoryManager.record_event(beat.on_complete_event)
	# 解除 signal
	if ui:
		if ui.beat_advance_requested.is_connected(_on_advance):
			ui.beat_advance_requested.disconnect(_on_advance)
		if ui.beat_choice_made.is_connected(_on_choice_made):
			ui.beat_choice_made.disconnect(_on_choice_made)
	_active_beat = null
	_line_index = 0
	_ui = null
	print("BeatRunner: finished beat '%s'" % beat.beat_id)
	beat_finished.emit(beat.beat_id)
	if ui:
		ui.close_dialogue()
