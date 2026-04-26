## Chapter 01 Arrival — 章節事件
##
## 監聽：玩家與陳阿姨對話 → 標記章節完成 flag
extends RefCounted

func register(_manager: Node) -> void:
	StoryManager.event_recorded.connect(_on_event_recorded)

func unregister(_manager: Node) -> void:
	if StoryManager.event_recorded.is_connected(_on_event_recorded):
		StoryManager.event_recorded.disconnect(_on_event_recorded)

func _on_event_recorded(event_id: String) -> void:
	if event_id == "talked_to_chen_ayi":
		StoryManager.player_flags["chapter_completed_ch01_arrival"] = true
		ChapterManager.complete_current()
