# Maps — 場景地圖系統

混合式架構：地形用 TileMap 拼貼、大型裝飾物用獨立 Prop 場景。

## 目錄結構

```
game/
├── assets/textures/environment/
│   ├── tilesets/              # 源圖：tileset PNG（可重複拼貼的地面/牆）
│   │   ├── nccu/              #   政大
│   │   ├── market/            #   木柵市場
│   │   ├── riverside/         #   道南河濱
│   │   └── zhinan/            #   指南山
│   └── props/                 # 源圖：獨立裝飾物 PNG
│       ├── nature/            #   樹、灌木、花圃
│       └── urban/             #   長椅、路燈、公告欄、垃圾桶
│
└── src/maps/
    ├── main_world.tscn        # 主世界容器（已存在）
    ├── tilesets/              # TileSet .tres 資源（地形素材定義）
    │   └── <zone>_tileset.tres
    ├── props/                 # 可重用的 Prop 場景
    │   ├── nature/            #   Tree.tscn, Bush.tscn 等
    │   └── urban/             #   Bench.tscn, LampPost.tscn 等
    └── zones/                 # 各場景的實例（已存在）
        ├── zone_nccu.tscn
        ├── zone_market.tscn
        ├── zone_riverside.tscn
        └── zone_zhinan.tscn
```

## 工作流程

### 1. 新增 tile 素材（地形）

1. 將 tileset PNG 放到 `assets/textures/environment/tilesets/<zone>/`
2. Godot 編輯器中建立 TileSet 資源存到 `src/maps/tilesets/<zone>_tileset.tres`
3. 在 Zone 場景中加入 `TileMapLayer` 節點、掛上該 TileSet

### 2. 新增 Prop（裝飾物）

1. 將 PNG 放到 `assets/textures/environment/props/<category>/`
2. 在 `src/maps/props/<category>/` 建立場景（Node2D + Sprite2D，必要時加 StaticBody2D）
3. 在 Zone 場景中用拖拉的方式實例化該 Prop

## Zone 場景標準結構

```
ZoneNCCU (Node2D)
├── TileMapLayer_Ground         # 地磚、草地（無碰撞）
├── TileMapLayer_Walls          # 牆、柵欄（含碰撞）
├── YSortRoot (Node2D, y_sort)  # Y 排序層 — 解決 NPC 與裝飾物前後遮擋
│   ├── Props                   #   實例化的樹、長椅、路燈
│   ├── NPCs                    #   NPC
│   └── Player                  #   玩家
└── Transitions                 # 換場區域
```

## 設計原則

- **地形用 TileMap**：磚牆、草地、地磚、柵欄 — 任何需要重複拼貼的內容
- **裝飾物用獨立場景**：樹、路燈、公告欄 — 尺寸不規則、可能需要互動、需要 Y-sort
- **Y-sort 放在 `YSortRoot` 層**：所有會被 NPC/Player 遮擋或遮擋 NPC/Player 的東西都要在此層下
- **碰撞分層**：牆/裝飾物的碰撞統一用 `StaticBody2D`，層號依 `game/src/core/` 定義的規範

## 相關資源

- **美術組提交素材指南**：`game/assets/textures/environment/如何提交地圖素材說明書.md`
- 角色 Spritesheet 流程：`game/assets/textures/characters/如何使用角色素材(Skins)說明書.md`
- Zone 換場機制：`game/src/core/classes/ZoneManager.gd`
