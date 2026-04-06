## ScreenTransition — 場景切換淡入淡出效果
## 使用 ColorRect + Tween 實現全畫面黑色遮罩過渡。
class_name ScreenTransition
extends CanvasLayer

signal fade_finished

@onready var _overlay: ColorRect = $Overlay

const FADE_DURATION: float = 0.4

func _ready() -> void:
	layer = 100  # 確保在最上層
	_overlay.color = Color(0, 0, 0, 0)
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE

## 淡出（畫面變黑）
func fade_out() -> void:
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	var tween: Tween = create_tween()
	tween.tween_property(_overlay, "color:a", 1.0, FADE_DURATION)
	await tween.finished
	fade_finished.emit()

## 淡入（畫面恢復）
func fade_in() -> void:
	var tween: Tween = create_tween()
	tween.tween_property(_overlay, "color:a", 0.0, FADE_DURATION)
	await tween.finished
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fade_finished.emit()
