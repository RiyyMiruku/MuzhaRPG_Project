## QuestManager — 任務追蹤系統
## 管理任務的接取、進度追蹤、完成判定。
extends Node

# ── Signals ─────────────────────────────────────────────────────────────────
signal quest_started(quest_id: String)
signal quest_completed(quest_id: String)
signal quest_available(quest_id: String)

# ── State ───────────────────────────────────────────────────────────────────
var _all_quests: Dictionary = {}           # quest_id -> QuestData
var _active_quests: Array[String] = []     # 進行中的任務
var _completed_quests: Array[String] = []  # 已完成的任務

func _ready() -> void:
	# 載入所有任務資源
	_load_all_quests()
	# 監聽事件，自動檢查任務完成條件
	StoryManager.event_recorded.connect(_on_event_recorded)

func _load_all_quests() -> void:
	var quest_dir: String = "res://src/quests/"
	if not DirAccess.dir_exists_absolute(quest_dir):
		return
	var dir: DirAccess = DirAccess.open(quest_dir)
	if dir == null:
		return
	dir.list_dir_begin()
	var file_name: String = dir.get_next()
	while file_name != "":
		if file_name.ends_with(".tres"):
			var quest: QuestData = load(quest_dir + file_name) as QuestData
			if quest and not quest.quest_id.is_empty():
				_all_quests[quest.quest_id] = quest
		file_name = dir.get_next()
	dir.list_dir_end()
	print("QuestManager: loaded %d quests" % _all_quests.size())

# ── Public API ──────────────────────────────────────────────────────────────
func start_quest(quest_id: String) -> bool:
	if _active_quests.has(quest_id) or _completed_quests.has(quest_id):
		return false
	if not _all_quests.has(quest_id):
		push_warning("QuestManager: Unknown quest: " + quest_id)
		return false
	var quest: QuestData = _all_quests[quest_id]
	# 檢查前置條件
	for req: String in quest.required_events:
		if not StoryManager.completed_events.has(req):
			return false
	_active_quests.append(quest_id)
	quest_started.emit(quest_id)
	print("QuestManager: quest started - ", quest.title)
	return true

func complete_quest(quest_id: String) -> void:
	if not _active_quests.has(quest_id):
		return
	_active_quests.erase(quest_id)
	_completed_quests.append(quest_id)
	var quest: QuestData = _all_quests[quest_id]
	# 發放獎勵
	_apply_rewards(quest)
	quest_completed.emit(quest_id)
	print("QuestManager: quest completed - ", quest.title)

func is_quest_active(quest_id: String) -> bool:
	return _active_quests.has(quest_id)

func is_quest_completed(quest_id: String) -> bool:
	return _completed_quests.has(quest_id)

func get_active_quests() -> Array[QuestData]:
	var result: Array[QuestData] = []
	for qid: String in _active_quests:
		if _all_quests.has(qid):
			result.append(_all_quests[qid])
	return result

func get_quest(quest_id: String) -> QuestData:
	return _all_quests.get(quest_id, null)

# ── Internal ────────────────────────────────────────────────────────────────
func _on_event_recorded(event_id: String) -> void:
	# 檢查是否有任務因此事件完成
	for qid: String in _active_quests.duplicate():
		var quest: QuestData = _all_quests[qid]
		if _check_completion(quest):
			complete_quest(qid)
	# 檢查是否有新任務可接取
	for qid: String in _all_quests:
		if _active_quests.has(qid) or _completed_quests.has(qid):
			continue
		var quest: QuestData = _all_quests[qid]
		var can_start: bool = true
		for req: String in quest.required_events:
			if not StoryManager.completed_events.has(req):
				can_start = false
				break
		if can_start:
			start_quest(qid)  # 自動接取符合條件的任務

func _check_completion(quest: QuestData) -> bool:
	for evt: String in quest.completion_events:
		if not StoryManager.completed_events.has(evt):
			return false
	return true

func _apply_rewards(quest: QuestData) -> void:
	for npc_id: String in quest.reward_relationship:
		var delta: int = quest.reward_relationship[npc_id]
		StoryManager.update_relationship(npc_id, delta)
	if not quest.reward_unlock_zone.is_empty():
		StoryManager.unlock_zone(quest.reward_unlock_zone)
	if not quest.reward_event.is_empty():
		StoryManager.record_event(quest.reward_event)

# ── Persistence ─────────────────────────────────────────────────────────────
func serialize() -> Dictionary:
	return {
		"active_quests": _active_quests.duplicate(),
		"completed_quests": _completed_quests.duplicate(),
	}

func deserialize(data: Dictionary) -> void:
	_active_quests.assign(data.get("active_quests", []))
	_completed_quests.assign(data.get("completed_quests", []))
