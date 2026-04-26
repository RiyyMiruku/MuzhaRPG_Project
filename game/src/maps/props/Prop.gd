## Prop — 場景裝飾物共用基底類別
## 適用於樹、長椅、路燈、公告欄等獨立裝飾物。
## 放在 y_sort 層下，可選擇是否具備碰撞/互動。
class_name Prop
extends Node2D

## 是否阻擋玩家（樹、公告欄等多為 true；草叢、花圃多為 false）
@export var has_collision: bool = true
## 是否可互動（按 E 觸發），需子類別覆寫 _on_interact()
@export var is_interactable: bool = false
## 互動提示文字（例：「閱讀公告」）
@export var interact_prompt: String = ""
## 自動將 Sprite2D 的軸心對齊到圖片底部中央（Y-sort 用）。
## 美術依規格：圖片底部中央 = 腳底位置 → Prop.position 即代表角色站立的點。
@export var foot_anchor: bool = true

@onready var sprite: Sprite2D = $Sprite2D if has_node("Sprite2D") else null
@onready var collision_body: StaticBody2D = $StaticBody2D if has_node("StaticBody2D") else null
@onready var interact_area: Area2D = $InteractArea if has_node("InteractArea") else null

func _ready() -> void:
	if foot_anchor and sprite != null and sprite.texture != null:
		var tex_size: Vector2 = sprite.texture.get_size()
		sprite.offset = Vector2(0, -tex_size.y / 2.0)
	if collision_body != null:
		collision_body.visible = has_collision
		collision_body.process_mode = Node.PROCESS_MODE_INHERIT if has_collision else Node.PROCESS_MODE_DISABLED
	if interact_area != null and is_interactable:
		interact_area.body_entered.connect(_on_player_entered)
		interact_area.body_exited.connect(_on_player_exited)

## 子類別覆寫此方法以定義互動行為（例：觸發對話、開啟 UI）
func _on_interact() -> void:
	pass

func _on_player_entered(body: Node) -> void:
	if body.is_in_group("player"):
		EventBus.prop_interact_available.emit(self, interact_prompt)

func _on_player_exited(body: Node) -> void:
	if body.is_in_group("player"):
		EventBus.prop_interact_unavailable.emit(self)
