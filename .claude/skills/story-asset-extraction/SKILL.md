---
name: story-asset-extraction
description: Use when the user provides chapter text, scene description, story draft, or screenplay snippet for this MuzhaRPG project and wants to identify which visual game assets need to be generated. Triggers on requests like "看這段劇本要哪些角色 / 素材", "從劇情挑出要生的圖", "我想做第一章的素材清單", "what assets does this scene need". Skips for already-decided asset lists, debugging, or non-extraction tasks. Upstream of the art-pipeline skill.
---

# 從劇情文本抽取美術資產規格

把章節劇本轉成兩份檔案，作為**素材歸屬的單一事實來源**：

1. `zones.json` —— 該章所有發生場景（zone slug + 中文標題 + 時期）
2. `assets.json` —— 每個素材附 `zones[]`（具體哪些場景會用到）+ type / name / category / Pixellab-ready description

下游 (`art-pipeline` + sync 腳本) 會把 `zones[]` 寫進 `art_source/<asset>/asset.json` 的 tags，Dashboard / Godot 都從那邊讀。**改場景配置只動本 skill 產出的兩份檔案。**

**你的位置**：

```
story/chapters/<slug>/draft.md  劇本草稿
      │
      ▼
  [story-asset-extraction] ← 本 skill（SSOT 起點）
      │
      ├─→ zones.json   (場景清單)
      └─→ assets.json  (素材 ↔ zones[] 對應)
      │
      ▼
  [art-pipeline] ← 下游 skill
      │
      ▼
  art_source/<asset>/asset.json (tags 含 zone:zone_xxx)
      │
      ▼
  Pixellab API + Dashboard 過濾
```

## 四階段流程

```
0. Scenes & Cast      — 通讀劇本，先列場景 + 跨場景主角（top-down）
1. Per-scene inventory — 逐場景列出該場景需要的素材（可 fan out subagents）
2. Classify            — 每個素材決定 asset type
3. Promptify           — 每個素材寫成 Pixellab-ready prompt
```

完成後輸出 `zones.json` + `assets.json` + `assets.md`，使用者點頭再丟給 art-pipeline。**不要直接呼叫 Pixellab 或 dashboard API**。

## Stage 0 — Scenes & Cast（場景與主角推演）

**先 top-down 一次過**，把章節骨架定下來。其餘階段都依賴這個結果。

### 0a. 列場景（zones）

讀完 `draft.md` + 章節 README/notes，列出本章**所有玩家會進入的場景**。每個場景一個 slug：

- 命名：`zone_<地點>_<時期或狀態>`，全小寫底線。例：
  - `zone_pharmacy_1983` (1983 年中藥行內部)
  - `zone_pharmacy_modern` (現代廢棄藥行)
  - `zone_market_1983` (1983 木柵市場街景)
  - `zone_apartment_muzha` (現代老公寓)
- 同一地點不同時期 → **不同 zone**（玩家會跨時空切換，素材氛圍不同）
- 室內 / 室外切割 → **不同 zone**（gameplay 上是不同 tscn）

寫進 `story/chapters/<slug>/zones.json`：

```json
{
  "chapter": "1",
  "chapter_slug": "chapter_01_arrival",
  "zones": [
    {
      "slug": "zone_pharmacy_1983",
      "title": "榮昌中藥行（1983 內部）",
      "period": "1983",
      "notes": "主要劇情舞台、配藥教學、與祖父互動"
    },
    {
      "slug": "zone_pharmacy_modern",
      "title": "榮昌中藥行（現代、廢棄）",
      "period": "modern",
      "notes": "開場、穿越觸發點、現代線蒐證"
    }
  ]
}
```

### 0b. 列主要角色（cast）

跨場景出現的核心 NPC + 玩家：

- 玩家控制角色（protagonist）
- 跨多個 zone 的具名 NPC（主要家族、關鍵 NPC）

這些角色的 `zones: ["*"]`（sentinel：任何 zone 都算）。**不要列全 zone slug**，否則新增 zone 還要回頭補。

場景專屬 NPC（只在某 zone 出現的攤販、路人、客人）留到 Stage 1 處理。

## Stage 1 — Per-scene inventory（逐場景列素材）

對 Stage 0 的每個 zone，列出**該場景畫面上會出現的東西**：

- 場景專屬 NPC（攤販、客人、路人）
- 場景元素：建築、攤車、桌椅、燈籠、招牌、樹、信箱、石頭...
- 地面 / 地形：草地、水泥路、河岸、磁磚、木地板...
- 動物（也走 character pipeline）

**不要過度推論**——文本沒提到的別腦補。但同質物件可以合併（「市場攤位 ×3」當一筆）。

### 可用 subagent 並行（場景多時）

如果章節有 5+ 個 zone，**用 superpowers:dispatching-parallel-agents skill** 對每個 zone 發一個 agent：

- 輸入：draft.md 全文 + 該 zone 的 slug/title/notes + Stage 0 已決定的主角清單
- 任務：「只列**這個 zone** 會出現的素材（含場景專屬 NPC、props、tileset），用結構化清單回」
- 主流程收齊各 zone 回覆 → merge

**Merge 規則**：同一素材在多個 zone 出現 → **合併成一筆**，`zones` 陣列列出所有出現的 zone slug。例：
- `medicine_cabinet_dusty` 出現在 zone_pharmacy_1983 + zone_pharmacy_modern（雖然氛圍不同，但同一個 prop instance 重用） → `zones: ["zone_pharmacy_1983", "zone_pharmacy_modern"]`
- 反例：1983 跟現代用的是**不同的 prop**（廢棄版有蜘蛛網、生鏽）→ 拆成 `medicine_cabinet_new` + `medicine_cabinet_dusty` 兩筆

### 場景數少（≤4）直接做

不用發 subagent，主流程逐場景列即可。

## Stage 2 — Classify（決定 asset type）

### Character classification — 嚴禁隨意抽 moving NPC

Moving NPC（8-dir + walk template）成本是 static NPC（4-dir + idle template）的 **2-3 倍** Pixellab token。預設 static，**只在下面三條優先級匹配時**才升級為 moving：

| 優先級 | 升 moving 的條件 | 範例 |
|:---:|---|---|
| **A** | 玩家控制角色（protagonist / playable） | `lin_siqian` (主角) |
| **B** | 劇本明確寫他在某場景**走動**（不是只進進出出畫面） | 「林小威跑出店門口」「老周從後院走來」 |
| **C** | World-building NPC，需要在地圖上**自由走動 / patrol** 增添場景動態感 | 市場攤販在攤位前後巡視、小孩在巷子追逐 |

**判斷流程**：每個 character 從上到下檢查 A → B → C，**任一條成立才升 moving**，否則 static。「家族成員」「shopkeeper 主要在櫃台」這類**不是**自動升 moving 的理由。

### 完整分類表

| 文本中的描述 | Asset type | Orchestrator | Notes |
|---|---|---|---|
| 通過上面 A/B/C 任一條 | **moving NPC** | `npc_moving.py` | 8 向 walk + 4 向 idle |
| 具名 NPC 但都站著 / 坐著 / 偶爾移動畫面外 | **static NPC** | `npc_static.py --directions 4` | 4 向 idle，預設選擇 |
| 不確定會不會走動但**有可能**未來章節升 moving | **static NPC** | `npc_static.py --directions 8` | 留 8 向 base，將來只補 walk animation 不重生 base |
| 路人 / 群眾（無具名） | **static NPC** | `npc_static.py --directions 4` | 一個泛用 NPC 多次擺放 |
| 單一場景物件（燈籠、攤車、桌、信箱） | **iso prop** | `prop.py --kind=iso_prop --size 32` | 視大小調 size |
| 建築（店、廟、宿舍） | **iso building** | `prop.py --kind=iso_building` | isometric 視角，與街景一致 |
| 地形（草、磚、水、沙） | **autotile** | `autotile.py` | Wang 4×4，要 lower + upper 兩種地形 |

**Edge case 判斷**：
- 「會跟玩家對話一次後消失」→ static NPC 即可（省 credit）
- 「主線角色但本章不走動」→ static NPC `--directions 8`（未來升 moving 不用整支重生）
- 「敘事中提到背影」→ 還是 8-dir base（rotation 系統設計如此）
- 「大型建築需要走進去」→ building 是外殼，室內另開 zone（兩個 zone 都掛這 building 的 zones[]，因為街景跟室內入口都會看到外觀）

### Moving 抽過頭的代價

Chapter 1 第一輪抽取把家族 + 市場核心 6 個都標 moving，事後檢視只有 `lin_siqian`(A) + `lin_xiaowei`(B) 真的需要；`lin_ama` / `a_tao_yi` / `lin_rongchang` / `chen_xiuqin` 4 個都是「好像會動所以給 walk」的腦補，浪費 ~30 Pixellab generations。**新章節抽取避免重蹈**。

## Stage 3 — Promptify（寫 Pixellab prompt）

### 命名（manifest 鍵）
- 通過 regex `^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`（長度 3–64）
- 具名 NPC：`chen_ayi`、`lin_zhiwei` —— 拼音 + 底線
- 泛用 NPC：`vendor_market_01`、`student_nccu_03` —— 帶角色屬性 + 編號
- Tileset：`market_grass_asphalt`、`riverside_water_sand`
- Building：`pharmacy_rongchang_1983`、`market_shophouse_minnan`
- Iso prop：`lantern_red`、`cart_fruit`
- **不要**在 name 裡放 zone（已有 `zones[]` 欄位）

### Zones / Category / Chapter 欄位

- **`zones`**: 陣列，列出該素材出現的**所有 zone slug**（Stage 0 列舉的）
  - 場景專屬：`["zone_pharmacy_1983"]`
  - 多場景共用：`["zone_pharmacy_1983", "zone_pharmacy_modern"]`
  - 跨章節 / 跨全部 zone（主角、UI 元素）：`["*"]` sentinel
  - **每個 slug 必須在 zones.json 中存在**（除了 `*`）
- **`category`**: 自由形 —— `vendor`, `student`, `monk`, `building`, `decoration`, `terrain`, ...
- **`chapter`**: 劇情時序，**必填**（top-level，不在每筆素材重複）。從 `draft.md` 所在資料夾名取（例：`chapter_01_arrival` → `chapter: "1"`）

**Tag 同步方向（單向）**：本 skill 寫的 `assets.json` → sync 腳本 → `art_source/<asset>/asset.json` 的 `tags`（每個 zone 一個 `zone:zone_xxx` tag）。**反向不同步**。

### Prompt 寫作慣例（Pixellab v2）

**Character description**：
- **語言**：英文（Pixellab 是英文訓練）
- **排序**：年齡 → 性別 / 族裔 → 體型 → 上衣 → 下身 → 鞋 → 髮型 → 表情 → 配件 → **arms relaxed at sides**（與 idle/walk 預設姿態 default prompt 一致）
- **避免**：copyrighted IP 名、品牌 logo、暴力 / 血腥、不對稱裝飾（會放大 head-turn 問題）
- **族裔**：本作背景台北木柵，預設 `taiwanese`，例外角色才換
- **範例**：
  ```
  middle-aged taiwanese market vendor woman, plump build, red floral
  shirt, beige apron, dark trousers, black canvas shoes, short curly
  permed hair, warm smile, gold hoop earrings, arms relaxed at sides
  ```

**Iso prop / building description**：
- 直接描述物件特徵與材質
- 建築指明風格（`traditional taiwanese`, `post-war concrete`, `japanese colonial`）
- iso building 描述記得帶 isometric / 30-degree 提示（Pixellab `/create-image-pixflux` `isometric` flag 是 weakly guiding）
- **範例**：
  ```
  isometric view of a traditional taiwanese two-story shophouse, red
  brick lower floor, white plastered upper floor, dark tile roof, faded
  chinese signboard, small balcony with iron railing, 30-degree angle
  ```

**Tileset**：兩個欄位
- `lower`：基礎 / 較常見的地面
- `upper`：覆蓋 / 較稀有的地面
- 可選 `transition_description`：兩者交界的過渡材質

### Idle / walk prompt override（character 才有）

預設用 art-pipeline 已包好的 default prompt。**只有當角色姿態需要明顯不同**才客製：
- 抱嬰兒 → idle prompt 改「arms cradling baby at chest」
- 推手推車 → walk prompt 改「both hands gripping cart handle in front」
- 拐杖老人 → walk prompt 改「leaning slightly on a wooden cane held in right hand」

沒這類特殊姿態就**完全省略**這兩個欄位。

## Output location（一律寫進 story/ 對應章節資料夾）

```
story/chapters/<chapter_slug>/
├── draft.md       ← 來源（你讀的）
├── zones.json     ← Stage 0a 產出，本章 zone 清單
├── assets.json    ← Stage 1-3 產出（machine-readable，給 art-pipeline 餵）
└── assets.md      ← assets.json 的人類版鏡像
```

`<chapter_slug>` 跟 `game/src/chapters/<slug>/` 對齊（例：`chapter_01_arrival`）。

如果使用者沒指定章節，先問：「這份劇本對應到哪個章節 slug？要建新的還是寫進現有的？」**不要自己猜或亂建**。

寫入後把摘要 + 檔案路徑貼回對話讓使用者審：

> 已寫入 `story/chapters/chapter_01_arrival/{zones,assets}.json` + `assets.md`。
> 場景 N 個：zone_pharmacy_1983 / zone_market_1983 / ...
> 素材 M 個（X moving NPC、Y static NPC、Z props、W buildings、V tilesets）。
> 確認後可叫 art-pipeline skill 餵 Dashboard。

## Output schema

### `zones.json`

```json
{
  "chapter": "1",
  "chapter_slug": "chapter_01_arrival",
  "zones": [
    {
      "slug": "zone_pharmacy_1983",
      "title": "榮昌中藥行（1983 內部）",
      "period": "1983",
      "notes": "主要劇情舞台"
    }
  ]
}
```

### `assets.json`

```json
{
  "chapter": "1",
  "chapter_slug": "chapter_01_arrival",
  "moving_npcs": [
    {
      "name": "lin_siqian",
      "description": "young taiwanese man, ...",
      "zones": ["*"],
      "category": "protagonist"
    }
  ],
  "static_npcs": [
    {
      "name": "lao_zhou",
      "directions": 4,
      "description": "elderly taiwanese man, ...",
      "zones": ["zone_market_modern"],
      "category": "elder"
    }
  ],
  "iso_props": [
    {
      "name": "medicine_cabinet_dusty",
      "size": 64,
      "description": "...",
      "zones": ["zone_pharmacy_modern"],
      "category": "furniture"
    }
  ],
  "buildings": [
    {
      "name": "pharmacy_rongchang_1983",
      "kind": "iso_building",
      "description": "isometric view of ...",
      "zones": ["zone_pharmacy_1983", "zone_market_1983"],
      "category": "building"
    }
  ],
  "tilesets": [
    {
      "name": "market_concrete_tile",
      "lower": "...",
      "upper": "...",
      "zones": ["zone_market_1983", "zone_market_modern"],
      "category": "terrain"
    }
  ]
}
```

**Top-level**：
- `chapter`: 必填，art-pipeline 批次跑時套到每筆 POST，不在每個 asset 重複
- `chapter_slug`: 給人類對齊資料夾用

**每筆 asset 的 `zones`**：必填陣列，至少一個元素。值必須是 `zones.json` 中列舉的 slug，或 sentinel `"*"`。

### `assets.md`（人類版鏡像）

```markdown
## 第一章資產清單

### Scenes (zones)
| slug | 中文 | 時期 |
|---|---|---|
| zone_pharmacy_1983 | 榮昌中藥行（1983） | 1983 |
| zone_pharmacy_modern | 榮昌中藥行（現代） | modern |

### Moving NPCs
| name | description | zones | category |
|---|---|---|---|
| lin_siqian | 主角 | * | protagonist |

### Static NPCs / Iso props / Buildings / Tilesets
(同樣格式，含 zones 欄)
```

## Handoff 到 art-pipeline skill

使用者點頭後，下一步**不是直接生**，而是切換到 [art-pipeline skill](../art-pipeline/SKILL.md)。

art-pipeline 會：
1. 餵 Dashboard job API（或 CLI for-loop）依 `assets.json` 批次生
2. 把 `zones[]` 寫進每個素材的 `art_source/<asset>/asset.json` `tags`（每個 zone 一個 `zone:zone_xxx` tag；`*` 也照 `zone:*` 寫，dashboard filter 端會特判）
3. 把 top-level `chapter` 寫進 `chapter:<n>` tag

漏帶 `chapter` 或 `zones` 的話 manifest 會少了溯源 / 過濾欄位，後續清理 / 重生會很痛。

## 不要做的事

- ❌ 直接呼叫 Pixellab API（art-pipeline 的責任）
- ❌ 自己腦補文本沒提到的角色或物件
- ❌ 用中文寫 description（Pixellab 是英文訓練）
- ❌ 在 name 裡塞 zone / category 資訊（已有獨立欄位）
- ❌ `zones` 寫不在 `zones.json` 列舉中的 slug
- ❌ 主角 / 跨章節元素列全 zone slug（用 `["*"]`）
- ❌ 替每個 character 都寫 idle/walk override（只有特殊姿態才寫）
- ❌ 用真實品牌 logo 或版權 IP 名稱
- ❌ 反向同步（從 `art_source/asset.json` 改回 `story/.../assets.json`）

## 範例（短篇 — 兩個場景）

**輸入文本**：
> 玩家阿謙站在 1983 年的榮昌中藥行內，祖父林榮昌在櫃台後配藥，藥櫃靠後牆三排。穿到現代後同一個藥行佈滿灰塵，櫃台還在但藥櫃積了厚厚一層灰，牆上有塗黑的全家福。

**輸出**（簡版）：

`zones.json`:
```json
{
  "chapter": "1",
  "chapter_slug": "chapter_01_arrival",
  "zones": [
    {"slug": "zone_pharmacy_1983", "title": "榮昌中藥行（1983）", "period": "1983"},
    {"slug": "zone_pharmacy_modern", "title": "榮昌中藥行（現代廢棄）", "period": "modern"}
  ]
}
```

`assets.json`:
```json
{
  "chapter": "1",
  "chapter_slug": "chapter_01_arrival",
  "moving_npcs": [
    {
      "name": "lin_siqian",
      "description": "young taiwanese man in his late twenties, ...",
      "zones": ["*"],
      "category": "protagonist"
    }
  ],
  "static_npcs": [
    {
      "name": "lin_rongchang",
      "directions": 4,
      "description": "middle-aged taiwanese man, beige apron, ...",
      "zones": ["zone_pharmacy_1983"],
      "category": "shopkeeper"
    }
  ],
  "iso_props": [
    {
      "name": "medicine_cabinet_new",
      "size": 64,
      "description": "wooden chinese medicine cabinet with many small drawers",
      "zones": ["zone_pharmacy_1983"],
      "category": "furniture"
    },
    {
      "name": "medicine_cabinet_dusty",
      "size": 64,
      "description": "abandoned wooden medicine cabinet covered in dust and cobwebs",
      "zones": ["zone_pharmacy_modern"],
      "category": "furniture"
    },
    {
      "name": "shop_counter_wood",
      "size": 48,
      "description": "long wooden shop counter with traditional carvings",
      "zones": ["zone_pharmacy_1983", "zone_pharmacy_modern"],
      "category": "furniture"
    },
    {
      "name": "family_photo_blacked",
      "size": 24,
      "description": "framed family photograph with faces blacked out, hung on wall",
      "zones": ["zone_pharmacy_modern"],
      "category": "decoration"
    }
  ],
  "buildings": [],
  "tilesets": []
}
```

注意：
- `lin_siqian` 主角 → `zones: ["*"]`
- `shop_counter_wood` 兩個時期共用同一個 prop → `zones: [..., ...]`
- `medicine_cabinet` 兩個版本拆開（氛圍差太多） → 各自 `zones: [...]`
- `family_photo_blacked` 只在現代版出現 → 單一 zone
