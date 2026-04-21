# Props — 獨立裝飾物場景

## 建立新 Prop 的步驟

1. 在 Godot 編輯器中開啟 `PropTemplate.tscn`
2. 「另存新檔」為對應類別資料夾下的具體 Prop（例如 `nature/Tree.tscn`）
3. 指定 `Sprite2D` 的 texture（指向 `assets/textures/environment/props/<category>/` 下的 PNG）
4. 調整 `StaticBody2D/CollisionShape2D` 的形狀（通常只擋下半部腳底，讓 Y-sort 看起來正確）
5. 視需求設定 Prop 腳本的 export 參數：
   - `has_collision`：是否阻擋玩家（樹 true、草叢 false）
   - `is_interactable`：是否可按 E 互動（公告欄 true、路燈 false）
   - `interact_prompt`：互動提示文字（如「閱讀公告」）

## 碰撞層規範

| Layer | 用途 |
| --- | --- |
| 1 | Player |
| 2 | NPC |
| 4 | Prop 靜態碰撞 |

`StaticBody2D.collision_layer = 4`, `collision_mask = 0`（prop 不主動偵測任何東西）
`InteractArea.collision_layer = 0`, `collision_mask = 1`（只偵測 Player）

## 可互動 Prop 範例

```gdscript
## BulletinBoard.gd
extends Prop

func _on_interact() -> void:
	EventBus.hud_message_requested.emit("今日公告：...", 3.0)
```

## Y-sort 對位

Sprite2D 的 `offset.y` 應設為「負的 sprite 高度的一半」，讓 Prop 的 y 座標代表腳底位置。
這樣 Y-sort 才能正確判斷前後順序。
