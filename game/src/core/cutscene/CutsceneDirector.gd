## CutsceneDirector — 跑 Cutscene.tres ops 的 director
##
## 掛在 main_world(類似 ZoneManager,非 autoload)。監聽 `EventBus.cutscene_requested`。
##
## 跑 cutscene 流程:
##   1. GameManager 切 DIALOGUE state(暫時複用,後續可加 CUTSCENE state)
##   2. 逐一執行 ops:
##      - line   → DialogueUI.show_beat_line + 等 beat_advance_requested
##      - wait   → await timer
##      - camera_to → spawn 高 priority PhantomCamera2D 到目標 + 等 duration
##      - restore_camera → 殺掉 cutscene cam → DefaultCam 自動奪回
##      - set_flag / emit_event → StoryManager
##      - era_switch → await EraManager.travel_to
##   3. 結束 → 關 DialogueUI、回 EXPLORING、emit cutscene_finished
##
## 設計準則:
##   - cutscene cam 用 `PhantomCamera2D` node + script ref,priority 100(壓 DefaultCam=0)
##   - cam blend tween 由 addon 自動處理;director 只需等該 op 的 duration
##   - 玩家 ESC 中止 → 立刻結束 op loop、做 cleanup
class_name CutsceneDirector
extends Node

signal cutscene_started(cutscene_id: String)
signal cutscene_finished(cutscene_id: String)

const PCAM_SCRIPT: GDScript = preload(
	"res://addons/phantom_camera/scripts/phantom_camera/phantom_camera_2d.gd"
)
const CUTSCENE_PRIORITY: int = 100

var _active: Cutscene = null
var _abort: bool = false
var _dialogue_ui: DialogueUI = null
var _current_zone_root: Node = null
var _cutscene_cam: Node2D = null

func _ready() -> void:
	EventBus.cutscene_requested.connect(_on_cutscene_requested)


# ── Public API ──────────────────────────────────────────────────────────────
func run(cutscene: Cutscene) -> void:
	if _active != null:
		push_warning("CutsceneDirector: cutscene '%s' running, ignoring '%s'" % [
			_active.cutscene_id, cutscene.cutscene_id
		])
		return
	_active = cutscene
	_abort = false
	_dialogue_ui = _find_dialogue_ui()
	_current_zone_root = _find_zone_root()
	GameManager.change_state(GameManager.GameState.DIALOGUE)
	cutscene_started.emit(cutscene.cutscene_id)

	for op: Dictionary in cutscene.ops:
		if _abort:
			break
		await _run_op(op)

	# Cleanup
	_cleanup_cam()
	if _dialogue_ui and _dialogue_ui.visible:
		_dialogue_ui.close_dialogue()
	GameManager.change_state(GameManager.GameState.EXPLORING)
	var finished_id: String = _active.cutscene_id
	_active = null
	cutscene_finished.emit(finished_id)


# ── Op Dispatch ─────────────────────────────────────────────────────────────
func _run_op(op: Dictionary) -> void:
	var kind: String = op.get("op", "")
	match kind:
		"line": await _op_line(op)
		"wait": await _op_wait(op)
		"camera_to": await _op_camera_to(op)
		"restore_camera": _op_restore_camera()
		"set_flag": _op_set_flag(op)
		"emit_event": _op_emit_event(op)
		"era_switch": await _op_era_switch(op)
		_: push_warning("CutsceneDirector: unknown op %s" % kind)

func _op_line(op: Dictionary) -> void:
	if _dialogue_ui == null:
		await get_tree().create_timer(1.0).timeout
		return
	# 第一句啟動 beat mode UI;後續直接 show_beat_line
	if not _dialogue_ui.visible:
		_dialogue_ui.open_beat_mode(_synth_dummy_beat())
	_dialogue_ui.show_beat_line({
		"speaker": op.get("speaker", "narrator"),
		"text": op.get("text", ""),
	})
	await _dialogue_ui.beat_advance_requested

func _op_wait(op: Dictionary) -> void:
	var seconds: float = float(op.get("seconds", 0.5))
	await get_tree().create_timer(seconds).timeout

func _op_camera_to(op: Dictionary) -> void:
	if _current_zone_root == null:
		return
	var target_path: String = op.get("target_path", "")
	var target: Node = _current_zone_root.get_node_or_null(target_path)
	if target == null:
		push_error("CutsceneDirector: camera_to target %s not found" % target_path)
		return
	_cleanup_cam()
	_cutscene_cam = Node2D.new()
	_cutscene_cam.name = "CutsceneCam"
	_cutscene_cam.set_script(PCAM_SCRIPT)
	_current_zone_root.add_child(_cutscene_cam)
	_cutscene_cam.set("priority", CUTSCENE_PRIORITY)
	_cutscene_cam.set("follow_mode", 1)   # GLUED
	_cutscene_cam.set("follow_target", target)
	var zoom_arr: Array = op.get("zoom", [6.0, 6.0])
	_cutscene_cam.set("zoom", Vector2(float(zoom_arr[0]), float(zoom_arr[1])))
	var duration: float = float(op.get("duration", 1.5))
	await get_tree().create_timer(duration).timeout

func _op_restore_camera() -> void:
	_cleanup_cam()

func _op_set_flag(op: Dictionary) -> void:
	var name_: String = op.get("name", "")
	if name_.is_empty(): return
	StoryManager.set_flag(name_, op.get("value", true))

func _op_emit_event(op: Dictionary) -> void:
	var name_: String = op.get("name", "")
	if name_.is_empty(): return
	StoryManager.record_event(name_)

func _op_era_switch(op: Dictionary) -> void:
	var target_era: String = op.get("era", "")
	if target_era.is_empty(): return
	await EraManager.travel_to(target_era)


# ── Helpers ─────────────────────────────────────────────────────────────────
func _cleanup_cam() -> void:
	if _cutscene_cam != null and is_instance_valid(_cutscene_cam):
		_cutscene_cam.queue_free()
	_cutscene_cam = null

func _find_dialogue_ui() -> DialogueUI:
	var root: Node = get_tree().current_scene
	if root == null: return null
	var ui: Node = root.find_child("DialogueUI", true, false)
	return ui as DialogueUI

func _find_zone_root() -> Node:
	var root: Node = get_tree().current_scene
	if root == null: return null
	var container: Node = root.find_child("ZoneContainer", false, false)
	if container == null or container.get_child_count() == 0:
		return null
	return container.get_child(0)

## DialogueUI.open_beat_mode 需要一個 StoryBeat;cutscene 沒有,合成空殼
func _synth_dummy_beat() -> StoryBeat:
	var b: StoryBeat = StoryBeat.new()
	b.beat_id = "cutscene_synth"
	b.dialogue_lines = []
	return b


# ── Event Bus ───────────────────────────────────────────────────────────────
func _on_cutscene_requested(cutscene_path: String) -> void:
	var res: Resource = load(cutscene_path)
	if res is Cutscene:
		run(res as Cutscene)
	else:
		push_error("CutsceneDirector: %s is not a Cutscene" % cutscene_path)
