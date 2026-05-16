## Cutscene — 編劇式 cutscene 序列 .tres
##
## 一個 Cutscene 是一串有序的 ops。CutsceneDirector 逐一執行。
##
## Ops schema(Dictionary):
##   {"op": "line",    "speaker": "narrator", "text": "..."}
##   {"op": "wait",    "seconds": 0.5}
##   {"op": "camera_to", "target_path": "YSortRoot/family_photo_blacked_modern",
##                       "zoom": [6.0, 6.0], "duration": 1.5}
##   {"op": "restore_camera"}      # 回 DefaultCam(follow Player)
##   {"op": "set_flag", "name": "saw_blacked_photo", "value": true}
##   {"op": "era_switch", "era": "1983"}
##   {"op": "emit_event", "name": "first_time_travel"}
##
## 觸發:`EventBus.cutscene_requested.emit("res://.../<name>.tres")`
class_name Cutscene
extends Resource

@export var cutscene_id: String = ""
@export var ops: Array[Dictionary] = []
## 是否在 cutscene 期間鎖玩家輸入(預設鎖)
@export var blocks_input: bool = true
