## HUD — 遊戲進行中的資訊顯示
## 顯示當前區域名稱、遊戲內時間、當前任務提示。
class_name HUD
extends Control

@onready var _zone_label: Label     = $TopBar/ZoneLabel
@onready var _time_label: Label     = $TopBar/TimeLabel
@onready var _quest_label: Label    = $QuestPanel/QuestLabel
@onready var _quest_panel: Control  = $QuestPanel
@onready var _message_label: Label  = $MessageLabel
@onready var _message_timer: Timer  = $MessageTimer

func _ready() -> void:
	_message_label.hide()
	_message_timer.timeout.connect(_on_message_timeout)

	EventBus.zone_loaded.connect(_on_zone_changed)
	EventBus.hud_message_requested.connect(show_message)
	QuestManager.quest_started.connect(_on_quest_changed)
	QuestManager.quest_completed.connect(_on_quest_changed)

	_update_quest_display()

func _process(_delta: float) -> void:
	if not visible:
		return
	_time_label.text = StoryManager._get_time_string()
	_zone_label.text = StoryManager.ZONE_DISPLAY.get(
		StoryManager.current_zone, StoryManager.current_zone)

func _on_zone_changed(_zone_id: String) -> void:
	_zone_label.text = StoryManager.ZONE_DISPLAY.get(
		StoryManager.current_zone, StoryManager.current_zone)

func _on_quest_changed(_quest_id: String) -> void:
	_update_quest_display()

func _update_quest_display() -> void:
	var active: Array[QuestData] = QuestManager.get_active_quests()
	if active.is_empty():
		_quest_panel.hide()
		return
	_quest_panel.show()
	var lines: Array[String] = []
	for q: QuestData in active:
		lines.append("- " + q.title)
	_quest_label.text = "\n".join(lines)

func show_message(text: String, duration: float = 2.0) -> void:
	_message_label.text = text
	_message_label.show()
	_message_timer.wait_time = duration
	_message_timer.start()

func _on_message_timeout() -> void:
	_message_label.hide()
