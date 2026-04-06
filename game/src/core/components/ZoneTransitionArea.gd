## ZoneTransitionArea — 區域切換觸發器
## 放置在區域邊界，玩家進入時觸發場景切換。
## 在 Godot 編輯器中設定 target_zone 和 entry_point。
class_name ZoneTransitionArea
extends Area2D

## 目標區域 ID（如 "zone_market"）
@export var target_zone: String = ""
## 進入目標區域的入口點（如 "from_nccu"）
@export var entry_point: String = "default"

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	# 設定碰撞：偵測 Player（layer 1）
	collision_layer = 0
	collision_mask = 1

func _on_body_entered(body: Node) -> void:
	if body is Player and not target_zone.is_empty():
		EventBus.zone_transition_requested.emit(target_zone, entry_point)
