## 章節事件腳本範本
##
## ChapterManager 會在章節 start 時 new() 一個實例並呼叫 register(manager)，
## 章節結束/切換時呼叫 unregister(manager)。
##
## 在這裡：
##   - 連接 EventBus / StoryManager 的 signal
##   - 註冊 quest 監聽
##   - 觸發初始 cutscene
##   - 移動 NPC 到章節指定位置
extends RefCounted

func register(_manager: Node) -> void:
	# 範例：聽玩家走進指定 zone 觸發 cutscene
	# EventBus.zone_entered.connect(_on_zone_entered)
	pass

func unregister(_manager: Node) -> void:
	# 範例：解除 signal 連接，避免章節切換後殘留邏輯
	# if EventBus.zone_entered.is_connected(_on_zone_entered):
	#     EventBus.zone_entered.disconnect(_on_zone_entered)
	pass
