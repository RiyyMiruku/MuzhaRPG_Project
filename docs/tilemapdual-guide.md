# TileMapDual 地形繪製指南

> 文檔導覽：[INDEX](INDEX.md) — **對象**：場景設計 / 程式。**用途**：地形系統設定與用法。
> Godot 4.6 + TileMapDual v5.0.2

本專案地形使用 [TileMapDual](https://github.com/GilaPixel/TileMapDual) addon。**所有 zone 的地形都用 TileMapDual 節點畫，不用原生 TileMapLayer + Terrain Set。**

## 為什麼用 TileMapDual？

| | 原生 TileMap Terrain Set | TileMapDual |
|---|---|---|
| 設定難度 | 16 tile × 9 點手點 = 144 次 | 0 點，preset 自動套用 |
| 邊界品質 | 容易破圖、跳磚 | 完美無縫（雙網格錯位演算法） |
| 繪製方式 | 選 terrain → 拼角落 bitmask | 像填色一樣，全滿方塊塗塗就好 |
| Pixellab 4×4 素材相容 | 需要寫一堆 peering bits | 用 `<any>` + FG terrain palette 直接刷 |

---

## 1. 概念

`TileMapDual` 是 `TileMapLayer` 的子類別（`extends TileMapLayer`），所以它本身就是一個可繪製的圖層；其 `_ready()` 會建一個內部 `Display` 子節點專門做雙網格視覺。

**結果**：你只需要一個 `TileMapDual` 節點，在它上面用 terrain palette 直接刷，邊界自動處理，不用另外的「邏輯層 / 視覺層」配對。

---

## 2. 場景設定（每個 zone 第一次設一次）

### 必要結構

```
ZoneXxx (Node2D)
├── Ground (ColorRect)              # 背景色塊佔位（畫好地形後可刪）
├── ZoneLabel (Label)
├── TileMapDual (TileMapLayer)      # 地形 — 唯一一個圖層
│     - material: ghost_material.tres (addon)
│     - tile_set: inline TileSet sub_resource
│     - script: tile_map_dual.gd (addon)
├── YSortRoot (Node2D, y_sort)
│   ├── Player
│   └── (NPC / Prop instances)
└── Transitions (Node2D)
```

### TileSet inline sub_resource 結構

每個 zone 的 TileMapDual 節點都使用一個**內嵌**的 TileSet（不是外部 .tres 檔），結構：

```gdscript
[sub_resource type="TileSet" id="TileSet_<zone>_dual"]
terrain_set_0/mode = 1                                  # Match Corners
terrain_set_0/terrain_0/name = "<any>"                  # universal background
terrain_set_0/terrain_0/color = Color(...)              # 紫色
terrain_set_0/terrain_1/name = "FG -<png_name>"         # 第 1 張 PNG 對應的 terrain
terrain_set_0/terrain_1/color = Color(...)
terrain_set_0/terrain_2/name = "FG -<png_name>"         # 第 2 張 PNG（如有）
sources/0 = SubResource("TileSetAtlasSource_<zone>_0")  # 第 1 張 PNG 的 atlas
sources/1 = SubResource("TileSetAtlasSource_<zone>_1")  # 第 2 張 PNG 的 atlas
```

每個 atlas source 有 16 個 tile，peering bits 按 zhinan 範本（即 TileMapDual `Standard` preset）排列：

```
       col0  col1  col2  col3
row0:  4     10    13    12
row1:  9     14    15    8
row2:  2     3     11    5
row3:  0     7     6     1
```

bit 1=TL、2=TR、4=BL、8=BR；數值是 atlas 對應的 terrain index（atlas_0 → terrain 1，atlas_1 → terrain 2）。

> 4 個現有 zone (market, nccu, riverside, zhinan) 都已經設好。新增 zone 時參考既有 zone 結構複製。

---

## 3. 日常繪製流程

1. 打開該 zone 的 `.tscn`
2. 場景樹點 **`TileMapDual`** 節點
3. 視窗下方 TileMap 面板 → 「**地形**」分頁
4. 左邊 palette 看到該 zone 的 terrain：
   - `<any>`（紫，universal background — 通常不直接刷）
   - `FG -autotile_xxx.png`（每張 PNG 一個）
5. 選一個 FG terrain，矩形或畫筆塗 — TileMapDual 自動拼接邊界
6. `Ctrl+S` 存檔

---

## 4. 加新的 autotile PNG 到既有 zone

例：要在 nccu 多加一張 `autotile_brick_path.png`：

1. PNG 丟 `game/assets/textures/environment/tilesets/nccu/`
2. `Ctrl+Shift+R` 重掃
3. 跟 AI 說「我加了 nccu 的 brick_path autotile，幫我加進 TileMapDual」，AI 會：
   - 把 PNG 加成新 ext_resource
   - 加新的 `TileSetAtlasSource` sub_resource，用 zhinan 範本的 peering bits
   - 在 inline TileSet 加 `terrain_2/name = "FG -autotile_brick_path.png"` 跟對應 source

也可以手動在 Godot 內加，但用腳本批次比較不會出錯。

---

## 5. 加新 zone

1. 在 `game/src/maps/zones/` 建 `zone_xxx.tscn`，照標準結構（Ground / ZoneLabel / TileMapDual / YSortRoot / Transitions）
2. 把 autotile PNG 丟 `game/assets/textures/environment/tilesets/<zone>/`
3. 跟 AI 說「我建了新 zone xxx，幫我設定 TileMapDual」 → AI 會生成 ext_resources、atlas sub_resources、inline TileSet、TileMapDual 節點

---

## 6. 常見問題

### Q: 場景樹只有 `TileMapDual` 沒有別的 layer，對嗎？
- 對。TileMapDual 自己就是一個 TileMapLayer，內部用 Display 子節點處理視覺，不需要另一個 sibling layer。

### Q: 為什麼不用外部 `.tres` 檔，要用內嵌 sub_resource？
- TileMapDual 工作流的 TileSet 配置（peering bits / terrain）跟一般 .tres 用法不一樣，內嵌讓配置跟 zone 場景綁在一起，不會被其他工具誤用。

### Q: 改 PNG 後 TileMapDual 沒更新？
- 在 TileMapDual 節點 Inspector 找 `Force Update`，或重啟編輯器。

### Q: 邊界出現空白／黑塊？
- 確認 PNG 大小是 64×64（4×4 個 16×16 tile）
- 確認 inline TileSet sub_resource 的 16 個 tile 都有完整 peering bits（位置缺漏會破圖）

### Q: 物理碰撞怎麼設？
- 在 inline TileSet sub_resource 內，對需要擋路的 tile（通常是純 FG = bitmask 15 的位置）加 `<col>:<row>/0/physics_layer_0/polygon_0/points = PackedVector2Array(...)`
- 在 [resource] 區段（zone 場景外的 TileSet 或 inline 都一樣）加 `physics_layer_0/collision_layer = 1`
- Player.collision_mask = 7（layer 1+2+4），會擋

### Q: TileMapDual 跟原生 Terrain Set 衝突嗎？
- 不衝突，但不要混用。本專案統一用 TileMapDual。

---

## 7. 跟舊工作流的差異

| | 舊（手動 peering bits + scaffold_zone.py） | 新（TileMapDual） |
|---|---|---|
| 場景 layer | 1 個 TileMapLayer_Ground | 1 個 TileMapDual |
| TileSet 配置位置 | 外部 `<zone>_terrain.tres` | 內嵌 zone 場景的 sub_resource |
| 設定 peering bits | 16 tile × 4 角手點，或 scaffold_zone.py 模板 | zhinan 範本一鍵複製 |
| 視覺品質 | 看 peering bits 標得多細 | 一律完美無縫 |
| 已刪除檔案 | `scripts/scaffold_zone.py` + `game/src/maps/tilesets/*_terrain.tres` | — |

---

## 8. 參考資料

- 套件官方：[TileMapDual GitHub](https://github.com/GilaPixel/TileMapDual)
- Pixellab autotile 規格：[1-asset-creation.md](../game/assets/textures/environment/1-asset-creation.md)
- 場景設計流程：[2-scene-design.md](../game/assets/textures/environment/2-scene-design.md)
- Addon 採用記錄：[addons.md](addons.md)
