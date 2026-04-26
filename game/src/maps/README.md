# Maps — 場景地圖系統

混合式架構：**地形用 autotile + TileMap**（Terrain Set 自動處理邊緣），**裝飾物用獨立 Prop 場景**（Y-sort + collision）。

## 目錄結構

```
game/
├── assets/textures/environment/
│   ├── 1-asset-creation.md      # 給生圖人：素材製作與歸檔
│   ├── 2-scene-design.md        # 給地圖設計人：在 Godot 中組場景
│   ├── 3-ai-prompt.md           # 給 AI：自動補 Godot 結構的 prompt
│   ├── tilesets/                # 源圖：autotile + 一般 tileset PNG
│   │   ├── nccu/                #   autotile_grass_asphalt.png …
│   │   ├── market/
│   │   ├── riverside/           #   autotile_water_concrete.png
│   │   └── zhinan/              #   autotile_dirt_stone.png, autotile_stone_path.png
│   └── props/                   # 源圖：獨立裝飾物 PNG（一物件一張）
│       ├── nature/              #   tree_*, bush_*, rock_* …
│       └── urban/                #   bench_*, lamp_*, lantern_* …
│
└── src/maps/
    ├── main_world.tscn          # 主世界容器
    ├── tilesets/                # TileSet .tres 資源
    │   ├── <zone>_terrain.tres  #   autotile + 地形（Terrain Set，16×16）
    │   └── <zone>_props.tres    #   （未來：手繪 atlas，若需要）
    ├── props/                   # 可重用的 Prop 場景
    │   ├── Prop.gd              #   基底類別（含腳底錨點、collision、互動）
    │   ├── PropTemplate.tscn    #   範本 — 新建 prop 從此繼承
    │   ├── nature/              #   tree_oak.tscn, bush_flower.tscn …
    │   └── urban/                #   bench_wood.tscn, lamp_street.tscn …
    └── zones/                   # 各場景實例
        ├── zone_nccu.tscn
        ├── zone_market.tscn
        ├── zone_riverside.tscn
        └── zone_zhinan.tscn
```

---

## 工作流程

### A. 新增地形（autotile）

1. **美術產出**：依 [1-asset-creation.md](../../assets/textures/environment/1-asset-creation.md) 用 Pixellab 生成 `autotile_<lower>_<upper>.png`（16×16 tile，4-tile grid 64×64）
2. **歸檔**：丟到 `assets/textures/environment/tilesets/<zone>/`
3. **建 TileSet**（Godot 編輯器）：
   - 建 `src/maps/tilesets/<zone>_terrain.tres`
   - Texture Region Size = `16×16`
   - Atlas 加入該 PNG
   - Terrain Sets → New Terrain Set → 設 mode = Match Sides 或 Match Corners
   - 為 4 格分別設 bitmask（哪邊是上層、哪邊是下層）
4. **掛進 Zone**：在 `zone_<name>.tscn` 加 `TileMapLayer_Ground` 節點，掛上 `<zone>_terrain.tres`
5. **繪圖**：用 Terrain 筆刷塗，Godot 自動算邊緣轉角

### B. 新增 Prop（裝飾物）

1. **美術產出**：依 [1-asset-creation.md](../../assets/textures/environment/1-asset-creation.md) 一物件一 PNG（背景透明、底部中央 = 腳底）
2. **歸檔**：丟到 `assets/textures/environment/props/{nature|urban}/`
3. **建 Prop 場景**（Godot 編輯器）：
   - 開 [PropTemplate.tscn](props/PropTemplate.tscn)，**Save As** 到 `src/maps/props/<category>/<name>.tscn`
   - Sprite2D.texture 指到該 PNG（`offset` 不用手調，[Prop.gd](props/Prop.gd) 會在 `_ready()` 自動依 `foot_anchor` 設）
   - StaticBody2D/CollisionShape2D 設好碰撞範圍（樹幹底部矩形、長椅整體矩形等）；不需碰撞的 Prop（草叢、花圃）把 `has_collision = false`
   - 互動類（公告欄、攤位）設 `is_interactable = true` + `interact_prompt`
4. **擺進 Zone**：把 `.tscn` 拖入 `zone_<name>.tscn` 的 `YSortRoot` 底下

---

## Zone 場景標準結構

```
ZoneNCCU (Node2D)
├── TileMapLayer_Ground          # 地磚、草地（無碰撞）— 用 autotile
├── TileMapLayer_Walls           # 牆、欄杆（layer 4 collision）— 一般 tileset
├── YSortRoot (Node2D, y_sort)   # Y 排序層
│   ├── Props (Node2D)           #   實例化的樹、長椅、路燈
│   ├── NPCs (Node2D)            #   NPC spawn
│   └── Player                   #   玩家（由 ZoneManager 注入）
└── Transitions (Node2D)         # 換場 Area2D
```

**關鍵**：地形 TileMapLayer 在 `YSortRoot` **之外**（地面不參與 Y-sort），確保渲染順序：Ground → Walls → YSortRoot 內物件依 y 排序。

---

## 設計原則

- **地形用 autotile**：地面、河堤、道路 — 用 Pixellab 生成、Terrain 筆刷塗
- **手繪 tileset 只給「重複的牆/欄杆」**：若需要的話，仍用同 zone 資料夾、單獨 .tres
- **裝飾物用獨立場景**：樹、路燈、公告欄 — 尺寸不規則、Y-sort、可能互動
- **腳底錨點**：Prop 的 `position` 代表角色站立的位置，[Prop.gd](props/Prop.gd) 自動處理 Sprite2D offset
- **碰撞分層**：玩家=1、NPC=2、Prop/牆=4

---

## 相關文件

- 給生圖人 — 素材製作：[1-asset-creation.md](../../assets/textures/environment/1-asset-creation.md)
- 給地圖設計人 — 場景組合：[2-scene-design.md](../../assets/textures/environment/2-scene-design.md)
- 給 AI 的 prompt 範本：[3-ai-prompt.md](../../assets/textures/environment/3-ai-prompt.md)
- 角色實裝流程：[art_source/characters/3-asset-usage.md](../../../art_source/characters/3-asset-usage.md)
- 章節制開發：[docs/chapter-development.md](../../../docs/chapter-development.md)
- Zone 換場機制：[ZoneManager.gd](../core/classes/ZoneManager.gd)
- Prop 基底：[Prop.gd](props/Prop.gd)
