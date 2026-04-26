# Props — 獨立裝飾物場景

本資料夾放各類 Prop 的 `.tscn` 場景。

**操作流程**：
- 大批匯入（一次十幾個變體）：[scripts/IMPORT_ASSETS_README.md](../../../../scripts/IMPORT_ASSETS_README.md)（場景設計人入口：[docs/SCENE_DESIGN_WORKFLOW.md](../../../../docs/SCENE_DESIGN_WORKFLOW.md)）
- 單張手動建：[2-scene-design.md](../../../assets/textures/environment/2-scene-design.md)
- 擺進 zone：[2-scene-design.md](../../../assets/textures/environment/2-scene-design.md) Step 4

本文僅記錄程式端契約（給程式組或客製化 Prop 行為時參考）。

---

## 基底類別：[Prop.gd](Prop.gd)

所有 Prop 場景都繼承 `Prop.gd`，提供以下 export 屬性：

| 屬性 | 預設 | 說明 |
| --- | --- | --- |
| `has_collision` | `true` | 是否阻擋玩家（樹/桿 true、草叢/花圃 false） |
| `is_interactable` | `false` | 是否可按 E 互動 |
| `interact_prompt` | `""` | 互動提示文字（例：「閱讀公告」） |
| `foot_anchor` | `true` | 自動將 Sprite2D offset 設成圖片底部中央 = 腳底（Y-sort 用） |

`foot_anchor = true` 時，[Prop.gd](Prop.gd) 會在 `_ready()` 自動把 `Sprite2D.offset.y` 設成 `-texture.height / 2`。**美術產出符合「腳底對齊圖片底部中央」規格的 PNG 即可，不需手動調 offset。**

---

## 碰撞層規範

| Layer | 用途 |
| --- | --- |
| 1 | Player |
| 2 | NPC |
| 4 | Prop 靜態碰撞 |

PropTemplate 已預設：

- `StaticBody2D.collision_layer = 4`、`collision_mask = 0`（prop 不主動偵測任何東西）
- `InteractArea.collision_layer = 0`、`collision_mask = 1`（只偵測 Player）

---

## 互動 Prop 範例

互動類 Prop 需建立子類別覆寫 `_on_interact()`：

```gdscript
## BulletinBoard.gd
extends Prop

func _on_interact() -> void:
    EventBus.hud_message_requested.emit("今日公告：...", 3.0)
```

並在場景中設 `is_interactable = true`、`interact_prompt = "閱讀公告"`。

---

## 高/長 Prop 的 collision 建議

| PNG 高度 | 建議 collision shape |
| --- | --- |
| ≤ 16 px（小物：花圃） | `has_collision = false`（可走過） |
| 17–48 px（中物：椅、燈） | 整體矩形 |
| > 48 px（高物：樹、電線桿） | 只設「**底部 16×16**」矩形，讓角色可走到上半部後方 |

讓玩家「能繞到電線桿後方」很重要 — 高 Prop 的 collision 不應與整張 sprite 同高。
