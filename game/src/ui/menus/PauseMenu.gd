## PauseMenu — 暫停選單
class_name PauseMenu
extends Control

@onready var _resume_btn: Button      = $Panel/VBox/ResumeButton
@onready var _save_btn: Button        = $Panel/VBox/SaveButton
@onready var _load_btn: Button        = $Panel/VBox/LoadButton
@onready var _settings_btn: Button    = $Panel/VBox/SettingsButton
@onready var _status_label: Label     = $Panel/VBox/StatusLabel
@onready var _time_label: Label       = $Panel/VBox/TimeLabel
@onready var _zone_label: Label       = $Panel/VBox/ZoneLabel

func _ready() -> void:
	UIManager.register("PauseMenu", self)
	_resume_btn.pressed.connect(_on_resume)
	_save_btn.pressed.connect(_on_save)
	_load_btn.pressed.connect(_on_load)
	_settings_btn.pressed.connect(_on_settings)

func _input(event: InputEvent) -> void:
	if GameManager.current_state == GameManager.GameState.DIALOGUE:
		return
	if event.is_action_pressed("pause"):
		if UIManager.current_panel == "PauseMenu":
			UIManager.pop()
		elif not UIManager.is_any_open:
			_update_info()
			UIManager.push("PauseMenu")
		get_viewport().set_input_as_handled()

func _update_info() -> void:
	_zone_label.text = "Location: " + StoryManager.ZONE_DISPLAY.get(StoryManager.current_zone, StoryManager.current_zone)
	_time_label.text = "Time: " + StoryManager._get_time_string()
	_load_btn.disabled = not GameManager.has_save(1)
	_status_label.text = ""

func _on_resume() -> void:
	UIManager.pop()

func _on_save() -> void:
	GameManager.save_game(1)
	_status_label.text = "Saved!"
	_load_btn.disabled = false

func _on_load() -> void:
	UIManager.pop_all()
	GameManager.load_game(1)

func _on_settings() -> void:
	UIManager.push("KeybindSettings")
