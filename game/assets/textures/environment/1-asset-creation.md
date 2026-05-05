# ① 素材製作與歸檔（給美術組生圖人）

> 文檔導覽：[../../../../docs/INDEX.md](../../../../docs/INDEX.md) — **對象**：美術 / 生圖人。**用途**：Pixellab 設定、命名規範、像素規格。

> **2026-05 更新**：autotile 與 prop 建議走新的 [Pixellab MCP pipeline](../../../../art_source/pipeline/README.md)，跟 Claude 說「建一張 grass+asphalt autotile」即可自動產出 + 投影 iso；本文的 Pixellab Web UI 流程仍可用，但 MCP 流程更省工。

本文涵蓋《MuzhaRPG》場景所需素材的**製作規格與歸檔流程**。完成後丟進對應資料夾即可，**不需要操作 Godot**。

> **大批匯入捷徑**：如果你一次有十幾張同類 prop（例如 16 種燈籠變體），不用一張張歸檔。直接全部丟到 `temp/<物件名>/` 下面，跟 AI 說「我在 temp/ 加了新素材，幫我跑 import_assets.py」。AI 會自動重命名、搬位、生成對應 Godot 場景。詳見 [docs/scene-design-workflow.md](../../../../docs/scene-design-workflow.md)。
>
> 本文是「規格」說明（PNG 怎麼產出才合格），那邊是「流程」說明（產出後怎麼進專案）。
>
> 後續流程（在 Godot 中組成場景）見 [② 場景製作流程](2-scene-design.md)。

---

## 0. 一頁總覽

| 類型         | 用途                                                  | 工具                        | 輸出                         | 存放位置                 |
| ------------ | ----------------------------------------------------- | --------------------------- | ---------------------------- | ------------------------ |
| **Autotile** | 會大面積拼貼 + 自動融合邊緣的地形（草地、道路、河堤） | Pixellab AI Tilesets        | 1 張 64×64 PNG（4 格 16×16） | `tilesets/<zone>/`       |
| **Prop**     | 單獨擺放、會擋住或被角色繞過的物件（樹、長椅、路燈）  | 自由（Aseprite / Pixellab） | 1 張獨立 PNG（背景透明）     | `props/{nature\|urban}/` |

**判斷哪一類**：

- 同樣的圖會在地圖上**重複拼貼**，且需要與另一種地形**自然融合**邊緣 → **Autotile**
- 單獨擺放、尺寸不規則、會擋住角色 → **Prop**
- 重複拼貼但**不需要邊緣融合**（如純磚牆段） → 也歸 Prop（單張獨立 PNG）

---

## 1. 生圖人工作流程

```
┌─────────────────┐
│ 1. 做素材       │  ← 章節 2 (autotile) / 章節 3 (Prop)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. 通用檢查     │  ← 章節 4：檔名、透明度、像素規格
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. 丟對應資料夾 │  ← tilesets/<zone>/  或  props/<category>/
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. 提交         │  ← 章節 6：commit / 打包
└─────────────────┘
```

**生圖人到 Step 4 結束就完成任務。** 場景組合（用 Godot 把素材擺進去）見 [② 場景製作流程](2-scene-design.md)，那部分大家都可以一起幫忙。

---

## 2. Autotile 製作

### 2.1 用 Pixellab AI 生成

**切到 Pixellab 的 `Tilesets` 標籤**（不是 Texture，不是 Maps）。

| 設定項                 | 值                                                           |
| ---------------------- | ------------------------------------------------------------ |
| Tile Size              | `16×16`                                                      |
| Map orientation        | `Top-down`                                                   |
| Lower Terrain          | 大面積基底，例：`green grass texture`                        |
| Upper Terrain          | 覆蓋層，例：`dark asphalt road texture`                      |
| Transition             | 銳利建築用 `None`；自然地形用 `Small (25%)` 或 `Large (50%)` |
| Transition Description | 邊緣描述（強烈影響細節），例：`grey concrete curb`           |

生成後**整張下載，不切分**，命名 `autotile_<lower>_<upper>.png`（例：`autotile_grass_asphalt.png`）。

### 2.2 四個 zone 推薦配方

| Zone                      | Lower                     | Upper                                                      | Transition    | Description                                   |
| ------------------------- | ------------------------- | ---------------------------------------------------------- | ------------- | --------------------------------------------- |
| 🏫 **nccu** 政大          | `green grass texture`     | `dark asphalt road texture` 或 `red brick pathway texture` | `Small (25%)` | `grey concrete curb`                          |
| ⛩️ **zhinan** 指南宮      | `brown dirt path texture` | `irregular stone path texture`                             | `Large (50%)` | `small pebbles and moss` 或 `overgrown weeds` |
| 🏞️ **riverside** 道南河濱 | `calm blue water surface` | `grey concrete riverbank`                                  | `Small (25%)` | `mossy concrete edge with small ripples`      |
| 🛒 **market** 木柵市場    | `rough concrete floor`    | `traditional market floor tiles`                           | `None`        | `cracked tiles showing concrete underneath`   |

### 2.3 歸檔

```
game/assets/textures/environment/tilesets/<zone>/autotile_<lower>_<upper>.png
```

**範例：** `tilesets/nccu/autotile_grass_asphalt.png`

> 一個 zone 可以有**多張** autotile（例：nccu 同時有草地+柏油、草地+紅磚兩張）。

---

## 3. Prop 製作

### 3.1 尺寸與構圖

- **單張 PNG 只放一個 Prop**（不要一張塞多個物件）
- 高度建議 ≤ 192 px（6 個 16-tile，避免遮太多畫面）
- 寬高建議對齊 16 px 倍數（方便擺位）
- 視角：**Low Top-down 微俯視** — 上半部偏側視（看得到樹冠/燈罩），下半部偏俯視（看得到底座）

### 3.2 腳底錨點（重要）

Prop 用 Y-sort 判斷遮擋順序，**腳底必須對齊圖片底部中央**：

```text
┌──────────────┐
│              │
│     🌳        │   ← 樹冠
│              │
│              │
│──────⚓──────│   ← 腳底錨點 = 圖片底部中央
└──────────────┘
```

**Prop 的 `position` 在程式端等於角色站立的點**。如果腳底沒對齊圖片底部中央，遮擋會錯位（角色會「穿樹幹」）。

底部如有陰影或落葉，**務必置中對稱**畫，不要偏左偏右。

#### 高/長 prop 怎麼處理（電線桿、長椅等）

PNG 多高都行（≤192 px 都在範圍）。例：電線桿 16×64（1×4 tiles 高）：

```text
┌────┐
│ ▒  │  ← 燈泡
│ ▒  │
│ │  │
│ │  │  ← 桿身
│ │  │
│ │  │
│ │  │
│ ╨  │  ← 底座
└─⚓──┘  ← 腳底錨點 = 底部中央
```

只要腳底錨點對齊底部中央，Y-sort 與遮擋會自動運作（程式端會處理 collision 與 offset，你不用管）。

### 3.3 透明度

- **必須 RGBA**（含 alpha 通道）
- 背景**完全透明**（α=0）
- 邊緣不殘留淡灰色羽化（Photoshop 匯出常見問題；可用「移除白邊」濾鏡或檢查 alpha 通道）

### 3.4 歸檔

```
game/assets/textures/environment/props/
├── nature/      # 自然類：樹、灌木、花圃、草叢、岩石、竹子、苔石
└── urban/       # 人造類：長椅、路燈、欄杆、公告欄、燈籠、垃圾桶、攤位、香爐、石碑
```

**判斷不確定時**：

- 主要由「自然界」生長/形成 → `nature/`
- 由「人」製造、會在城市出現 → `urban/`

---

## 4. 通用規範（兩類都要遵守）

### 4.1 檔名（**硬性**）

```
✅ 只允許：a-z A-Z 0-9 _ - .
✅ 必須以字母或數字開頭
```

| 違規類型   | 範例                       | 原因                        |
| ---------- | -------------------------- | --------------------------- |
| 中/日/韓文 | `樹.png`、`みどり.png`     | GitHub 跨平台 checkout 亂碼 |
| Emoji      | `tree🌳.png`               | Godot import 失敗           |
| 全形空白   | `tree　01.png`             | Python 讀檔不可靠           |
| 半形空白   | `my file.png`              | Shell / URL 處理麻煩        |
| 特殊符號   | `tree@home.png`、`a/b.png` | 檔系統非法字元              |

**命名規範：**

- Autotile：`autotile_<lower>_<upper>.png`（例：`autotile_grass_asphalt.png`）
- Prop：`<物件>_<編號>.png` 或 `<物件>_<材質>.png`（例：`tree_oak_01.png`、`bench_wood.png`）

### 4.2 像素風格

- Filter Mode 已在專案全局設為 **Nearest** — 不需手動設定
- **不要**用抗鋸齒、模糊、漸層柔邊（會讓像素風格破功）
- 色板維持 **32 色內**，與角色一致

### 4.3 透明度（再次強調）

- 全部素材**必須 RGBA PNG**
- 背景完全透明（α=0），不要填白或填黑

---

## 5. 提交前自檢清單

### Autotile

- [ ] Pixellab 設定為 `Tilesets` 標籤、Tile Size = 16×16、Top-down
- [ ] 整張下載，**未切分**
- [ ] 檔名格式 `autotile_<lower>_<upper>.png`
- [ ] 放在 `tilesets/<zone>/`

### Prop

- [ ] 一張 PNG 只放一個 Prop
- [ ] 背景完全透明（α=0），無灰邊
- [ ] **底部中央就是腳底位置**（Y-sort 用）
- [ ] 放在 `props/nature/` 或 `props/urban/`

### 通用（兩類都要過）

- [ ] 檔名純 ASCII，符合命名規範
- [ ] 像素風格（無抗鋸齒、無模糊）
- [ ] RGBA PNG

---

## 6. 提交

### 方式 A：直接 commit（會用 Git 的成員）

```bash
git add game/assets/textures/environment/
git commit -m "新增 nccu autotile 草地+柏油"
git push
```

### 方式 B：打包給程式組（不熟 Git）

1. 將素材按本文件的資料夾結構整理好
2. 壓縮成 zip 傳給程式組
3. 附上簡短說明（新增了什麼、替換了什麼）

---

## 下一步

素材交完後若你也想自己擺場景 → 看 [② 場景製作流程](2-scene-design.md)。

只交素材不擺場景也 OK，剩下交給其他人。
