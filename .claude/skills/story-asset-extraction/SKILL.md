---
name: story-asset-extraction
description: Use when the user provides chapter text, scene description, story draft, or screenplay snippet for this MuzhaRPG project and wants to identify which visual game assets need to be generated. Triggers on requests like "看這段劇本要哪些角色 / 素材", "從劇情挑出要生的圖", "我想做第一章的素材清單", "what assets does this scene need". Skips for already-decided asset lists, debugging, or non-extraction tasks. Upstream of the art-pipeline skill.
---

# 從劇情文本抽取美術資產規格

把章節劇本 / 場景描述轉成一份**可直接餵 art-pipeline 的資產清單**：每個資產附 type / name / zone / category / Pixellab-ready description（必要時加 idle/walk override）。

**你的位置**：

```
story/chapters/*.md  劇本草稿
      │
      ▼
  [story-asset-extraction] ← 本 skill
      │
      ▼
  資產清單 (JSON / Markdown)
      │
      ▼
  [art-pipeline] ← 下游 skill
      │
      ▼
  Pixellab API (Dashboard job API 批次或 CLI)
```

## 三階段流程

```
1. Inventory   — 通讀文本，列出所有出現的視覺實體（不分類，先全收）
2. Classify    — 每個實體決定 asset type（見下方 classification table）
3. Promptify   — 每個資產寫成 Pixellab-ready prompt（規格見後）
```

完成後輸出**結構化清單**給使用者確認，使用者點頭再丟給 art-pipeline skill。**不要直接呼叫 Pixellab 或 dashboard API** —— 那是 art-pipeline 的職責。

## Stage 1 — Inventory（抽視覺實體）

掃文本，列每個**會出現在畫面上**的東西。包含但不限於：

- 具名角色（會有對話的）
- 路人 / 背景人物（會出現但沒台詞的）
- 場景元素：建築、攤車、桌椅、燈籠、招牌、樹、信箱、石頭…
- 地面 / 地形：草地、水泥路、河岸、磁磚、木地板…
- 動物（也走 character pipeline）

**不要過度推論**——文本沒提到的別自己腦補。但同質物件可以合併（「市場攤位 ×3」當一筆，後續決定是 1 個 prop 出 3 次擺、還是 3 個 variant）。

## Stage 2 — Classify（決定 asset type）

| 文本中的描述 | Asset type | Orchestrator | Notes |
|---|---|---|---|
| 具名角色，會有走動 / 互動 | **moving NPC** | `npc_moving.py` | 8 向 walk + 4 向 idle |
| 具名背景 NPC，劇情中只站著 | **static NPC** | `npc_static.py --directions 4` | 4 向 idle |
| 不確定會不會走動的角色 | **static NPC** | `npc_static.py --directions 8` | 留 8 向給未來升級用 |
| 路人 / 群眾（無具名） | **static NPC** | `npc_static.py --directions 4` | 一個泛用 NPC 多次擺放 |
| 單一場景物件（燈籠、攤車、桌、信箱） | **iso prop** | `prop.py --kind=iso_prop --size 32` | 視大小調 size |
| 建築（店、廟、宿舍） | **building** | `prop.py --kind=building` | 用 high_top_down 視角，不投影 |
| 地形（草、磚、水、沙） | **autotile** | `autotile.py` | Wang 4×4，要 lower + upper 兩種地形 |

**Edge case 判斷**：
- 「會跟玩家對話一次後消失」→ static NPC 即可（省 credit）
- 「主線角色但短期內不會走動」→ static NPC `--directions 8`（未來升 moving 不用整支重生）
- 「敘事中提到背影」→ 還是 8-dir base（rotation 系統設計如此）
- 「大型建築需要走進去」→ building 是外殼；室內另開 zone

## Stage 3 — Promptify（寫 Pixellab prompt）

### 命名（manifest 鍵）
- 通過 regex `^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`（長度 3–64）
- 具名 NPC：`chen_ayi`、`lin_zhiwei` —— 拼音 + 底線
- 泛用 NPC：`vendor_market_01`、`student_nccu_03` —— 帶角色屬性 + 編號
- Tileset：`market_grass_asphalt`、`riverside_water_sand`
- Building：`nccu_dormitory`、`market_shophouse_01`
- Iso prop：`lantern_red`、`cart_fruit`
- **不要**在 name 裡放 zone（會走 `--zone` tag）

### Zone / Category tag
- `zone`：`market` | `nccu` | `riverside` | `zhinan` | `shared` | `test` —— 從劇本所在章節推斷
- `category`：自由形 —— `vendor`, `student`, `monk`, `building`, `decoration`, `terrain`, ...
- 不確定就先用 `shared`（共用素材）

### Prompt 寫作慣例（Pixellab v2）

**Character description**：
- **語言**：英文（Pixellab 是英文訓練）
- **排序**：年齡 → 性別 / 族裔 → 體型 → 上衣 → 下身 → 鞋 → 髮型 → 表情 → 配件 → **arms relaxed at sides**（與 idle/walk 預設姿態 default prompt 一致）
- **避免**：copyrighted IP 名（皮卡丘、初音）、品牌 logo、暴力 / 血腥、不對稱裝飾（會放大 head-turn 問題）
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
- **範例**：
  ```
  traditional taiwanese two-story shophouse, red brick lower floor,
  white plastered upper floor, dark tile roof, faded chinese signboard,
  small balcony with iron railing
  ```

**Tileset**：兩個欄位
- `lower`：基礎 / 較常見的地面
- `upper`：覆蓋 / 較稀有的地面
- 可選 `transition_description`：兩者交界的過渡材質
- **範例**：
  ```
  lower: weathered grey concrete sidewalk
  upper: green grass with small wildflowers
  transition: grey concrete curb edge
  ```

### Idle / walk prompt override（character 才有）

預設用 art-pipeline 已包好的 default prompt（head-lock + 手腕不亂甩）。**只有當角色姿態需要明顯不同**才客製，例如：
- 抱嬰兒 → idle prompt 改成「arms cradling baby at chest」
- 推手推車 → walk prompt 改成「both hands gripping cart handle in front」
- 拐杖老人 → walk prompt 改成「leaning slightly on a wooden cane held in right hand」

沒這類特殊姿態就**完全省略**這兩個欄位，讓 backend 用預設值。

## Output location（重要 — 一律寫進 story/ 對應章節資料夾）

抽完的清單**不要只貼在對話**，要落地成檔案：

```
story/chapters/<chapter_slug>/
├── draft.md       ← 來源（你讀的）
├── assets.json    ← 你寫這個（machine-readable，給 art-pipeline 餵）
└── assets.md      ← 也寫這個（人類版鏡像，給使用者 review）
```

`<chapter_slug>` 跟 `game/src/chapters/<slug>/` 對齊（例：`chapter_01_arrival`）。從 `draft.md` 所在的資料夾名直接取即可。

如果使用者沒指定章節，先問清楚：「這份劇本對應到哪個章節 slug？要建新的還是寫進現有的？」**不要自己猜或亂建**。

寫入後再把摘要貼回對話（前 5–10 項即可）讓使用者審，**並提示檔案路徑**，例：

> 已寫入 `story/chapters/chapter_01_arrival/assets.{json,md}`，共 N 項（M 個 NPC、K 個 prop…）。確認後可叫 art-pipeline skill 餵 Dashboard。

## Output schema（給使用者看的）

用 markdown 表格 + JSON code block 雙呈現（人類看表、AI / 腳本讀 JSON）：

````markdown
## 第一章資產清單（共 X 個）

### Moving NPCs
| name | description (摘要) | zone | category |
|---|---|---|---|
| chen_ayi | 中年市場攤販女性，紅花襯衫 | market | vendor |

### Static NPCs
| name | description (摘要) | directions | zone |
|---|---|---|---|
| vendor_market_01 | 老年水果商，草帽 | 4 | market |

### Iso props
| name | description (摘要) | size |
|---|---|---|
| lantern_red | 紅紙燈籠金穗 | 32 |

### Buildings
| name | description (摘要) | size |
|---|---|---|
| nccu_library | 政大圖書館外觀 | 128×128 |

### Tilesets
| name | lower | upper | transition |
|---|---|---|---|
| market_grass_asphalt | green grass | dark asphalt road | grey concrete curb |

---

```json
{
  "moving_npcs": [
    {
      "name": "chen_ayi",
      "description": "middle-aged taiwanese market vendor woman, ...",
      "zone": "market",
      "category": "vendor"
    }
  ],
  "static_npcs": [...],
  "iso_props": [...],
  "buildings": [...],
  "tilesets": [...]
}
```
````

## Handoff 到 art-pipeline skill

使用者點頭後，下一步**不是直接生**，而是切換到 [art-pipeline skill](../art-pipeline/SKILL.md)，由它判斷：

- Dashboard 在跑嗎？ → 用 job API 批次 queue
- Dashboard 沒跑？ → 退而求其次 CLI for-loop

把上面的 JSON 餵進 art-pipeline 的批次範本（見 art-pipeline SKILL.md「Dashboard job API 批次模式」段落）即可。

## 不要做的事

- ❌ 直接呼叫 Pixellab API（art-pipeline 的責任）
- ❌ 自己腦補文本沒提到的角色或物件
- ❌ 用中文寫 description（Pixellab 是英文訓練）
- ❌ 在 name 裡塞 zone / category 資訊（已有 tag 欄位）
- ❌ 替每個 character 都寫 idle/walk override（只有特殊姿態才寫）
- ❌ 用真實品牌 logo 或版權 IP 名稱

## 範例（短篇）

**輸入文本**：
> 阿姨站在木柵市場的水果攤後，身穿紅花襯衫戴著草帽，攤位掛著紅色紙燈籠。對面是傳統閩南式紅磚二樓街屋，地面是水泥地與雜草交界。阿姨身後跟著一隻黃色虎斑貓。

**輸出**（簡版示範重點）：

```json
{
  "static_npcs": [
    {
      "name": "vendor_market_ayi_01",
      "directions": 4,
      "description": "middle-aged taiwanese market vendor woman, plump build, red floral shirt with rolled sleeves, beige apron, dark slim trousers, black canvas shoes, short permed black hair, warm smile, straw conical hat, arms relaxed at sides",
      "zone": "market", "category": "vendor"
    },
    {
      "name": "cat_tabby_yellow",
      "directions": 4,
      "description": "small yellow tabby cat, fluffy fur, green eyes, sitting calmly, neutral expression",
      "zone": "market", "category": "animal"
    }
  ],
  "iso_props": [
    {
      "name": "lantern_red_market",
      "size": 32,
      "description": "red paper lantern with gold tassel, hung from wooden frame",
      "zone": "market", "category": "decoration"
    }
  ],
  "buildings": [
    {
      "name": "market_shophouse_redbrick",
      "width": 128, "height": 128,
      "description": "traditional taiwanese minnan two-story shophouse, red brick lower floor with arched doorway, white plastered upper floor with wooden window shutters, dark grey tile roof, weathered wooden signboard",
      "zone": "market", "category": "building"
    }
  ],
  "tilesets": [
    {
      "name": "market_grass_concrete",
      "lower": "weathered grey concrete pavement",
      "upper": "patchy green grass with small wildflowers",
      "transition_size": 0.25,
      "transition_description": "broken concrete edge mixed with soil",
      "zone": "market", "category": "terrain"
    }
  ]
}
```

把這份 JSON 連同使用者的確認交給 art-pipeline skill 就能批次跑了。
