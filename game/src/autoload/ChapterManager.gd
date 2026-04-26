## ChapterManager — 章節切換 + 章節差異套用的 autoload
##
## 職責：
##   1. 載入所有 ChapterConfig 並維護當前章節
##   2. 提供「給定 NPC ID → 取對應章節差異片段」介面（給 AIClient 使用）
##   3. 章節切換時 register/unregister 章節事件腳本
##   4. 監聽 StoryManager 事件，達成 completion_flags 後切下一章
##
## 章節資料夾位置：res://src/chapters/<chapter_id>/chapter.tres
extends Node

# ── Signals ────────────────────────────────────────────────────────────────
signal chapter_started(chapter: ChapterConfig)
signal chapter_completed(chapter: ChapterConfig)
signal chapter_changed(from_id: String, to_id: String)

# ── Constants ──────────────────────────────────────────────────────────────
const CHAPTERS_DIR: String = "res://src/chapters"

# ── State ──────────────────────────────────────────────────────────────────
var _all_chapters: Dictionary = {}             # chapter_id -> ChapterConfig
var _current: ChapterConfig = null
var _events_handler: RefCounted = null         # 當前章節 events 腳本實例

func _ready() -> void:
	_scan_chapters()

# ── 章節掃描 ───────────────────────────────────────────────────────────────
func _scan_chapters() -> void:
	var dir: DirAccess = DirAccess.open(CHAPTERS_DIR)
	if dir == null:
		push_warning("ChapterManager: %s not found, skipping scan" % CHAPTERS_DIR)
		return

	dir.list_dir_begin()
	var entry: String = dir.get_next()
	while entry != "":
		if dir.current_is_dir() and not entry.begins_with("."):
			var tres_path: String = "%s/%s/chapter.tres" % [CHAPTERS_DIR, entry]
			if ResourceLoader.exists(tres_path):
				var cfg: ChapterConfig = load(tres_path)
				if cfg != null and not cfg.chapter_id.is_empty():
					_all_chapters[cfg.chapter_id] = cfg
		entry = dir.get_next()
	dir.list_dir_end()
	print("ChapterManager: loaded %d chapters: %s" % [
		_all_chapters.size(), _all_chapters.keys()
	])

# ── 公開 API ───────────────────────────────────────────────────────────────
## 取得當前章節（可能是 null，遊戲剛啟動或自由模式）
func current() -> ChapterConfig:
	return _current

## 取得指定 NPC 在當前章節的對話差異片段（給 AIClient 組 prompt 用）
func get_npc_overlay(npc_id: String) -> String:
	if _current == null:
		return ""
	return _current.get_npc_overlay(npc_id)

## 該 NPC 在當前章節是否應出場
func is_npc_active(npc_id: String) -> bool:
	if _current == null:
		return true   # 沒章節 = 全部活躍（自由模式）
	return _current.includes_npc(npc_id)

## 切換到指定章節
func start_chapter(chapter_id: String) -> bool:
	if not _all_chapters.has(chapter_id):
		push_error("ChapterManager: unknown chapter '%s'" % chapter_id)
		return false

	var next_chapter: ChapterConfig = _all_chapters[chapter_id]
	if not _prerequisites_met(next_chapter):
		push_warning("ChapterManager: prerequisites not met for '%s'" % chapter_id)
		return false

	var prev_id: String = _current.chapter_id if _current != null else ""

	# 卸載舊章節
	if _current != null:
		_unregister_events()

	_current = next_chapter
	_register_events()

	chapter_changed.emit(prev_id, chapter_id)
	chapter_started.emit(_current)
	print("ChapterManager: started chapter '%s' (%s)" % [
		chapter_id, _current.display_name
	])
	return true

## 完成當前章節（內部觸發）
func complete_current() -> void:
	if _current == null:
		return
	chapter_completed.emit(_current)
	# 自動找下一章（order 為 current+1）
	var next: ChapterConfig = _find_next_in_order(_current.order)
	if next != null:
		start_chapter(next.chapter_id)

## 列出所有已載入章節（編輯器/測試用）
func list_all() -> Array:
	var arr: Array = _all_chapters.values()
	arr.sort_custom(func(a: ChapterConfig, b: ChapterConfig) -> bool:
		return a.order < b.order
	)
	return arr

# ── 內部 ───────────────────────────────────────────────────────────────────
func _prerequisites_met(chapter: ChapterConfig) -> bool:
	for prereq_id: String in chapter.prerequisites:
		# StoryManager 應有完成章節記錄；這裡先簡單用 player_flags
		var flag: String = "chapter_completed_" + prereq_id
		if not StoryManager.player_flags.get(flag, false):
			return false
	return true

func _register_events() -> void:
	if _current == null or _current.events_script == null:
		return
	_events_handler = _current.events_script.new()
	if _events_handler.has_method("register"):
		_events_handler.register(self)

func _unregister_events() -> void:
	if _events_handler != null and _events_handler.has_method("unregister"):
		_events_handler.unregister(self)
	_events_handler = null

func _find_next_in_order(current_order: int) -> ChapterConfig:
	var best: ChapterConfig = null
	for cfg: ChapterConfig in _all_chapters.values():
		if cfg.order > current_order:
			if best == null or cfg.order < best.order:
				best = cfg
	return best
