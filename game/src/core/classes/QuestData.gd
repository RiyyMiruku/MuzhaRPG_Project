## QuestData — 任務資料定義
## 每個任務對應一個 .tres 資源檔。
class_name QuestData
extends Resource

enum QuestStatus { LOCKED, AVAILABLE, ACTIVE, COMPLETED }

@export var quest_id: String = ""
@export var title: String = ""                     # 顯示名稱
@export var description: String = ""               # 任務描述
@export var giver_npc_id: String = ""              # 發放任務的 NPC
@export var target_zone: String = ""               # 任務目標區域（可選）
@export var target_npc_id: String = ""             # 任務目標 NPC（可選）

## 前置條件：需要完成哪些事件才能接取
@export var required_events: Array[String] = []
## 完成條件：需要哪些事件被觸發才算完成
@export var completion_events: Array[String] = []

## 完成後獎勵
@export var reward_relationship: Dictionary = {}   # npc_id -> int delta
@export var reward_unlock_zone: String = ""        # 解鎖區域
@export var reward_event: String = ""              # 觸發事件
