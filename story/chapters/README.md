# 故事章節 / 敘事工作區

這個資料夾放**敘事側**的章節內容（劇本、資產清單、設定筆記）。**程式側**（Godot 場景、beats、events.gd）在 [game/src/chapters/](../../game/src/chapters/)，兩邊用相同 slug 對齊。

## 結構

每個章節一個資料夾：

```
story/chapters/<slug>/
├── README.md       ← 章節入口：標題、狀態、流程提示
├── draft.md        ← 敘事草稿（劇情、角色、設定、主線）
├── assets.json     ← story-asset-extraction skill 產出的資產清單（machine-readable）
├── assets.md       ← 同上的人類版鏡像（給審稿用）
└── notes.md        ← 選填：角色 bio、worldbuilding、伏筆記事
```

`<slug>` 用 `chapter_NN_<keyword>` 形式（例：`chapter_01_arrival`、`chapter_02_market_fire`），**與 `game/src/chapters/<slug>/` 完全一致**。

## 流程

```
draft.md
    │
    ▼  story-asset-extraction skill
assets.json + assets.md  ← 使用者審 / 改
    │
    ▼  art-pipeline skill
Pixellab 批次生成 → art_source/ + game/assets/
    │
    ▼  人工
game/src/chapters/<slug>/ 寫 beats、events、NPCProfile
```

## 命名與分工

| 動作 | 在哪 |
|---|---|
| 寫劇本草稿 | `story/chapters/<slug>/draft.md` |
| 抽資產清單 | AI 透過 story-asset-extraction skill 寫進 `assets.json` |
| 跑美術 | AI 透過 art-pipeline skill 餵 Dashboard API |
| 寫 Godot 內容（場景、beat、events） | `game/src/chapters/<slug>/`，見 [docs/chapter-development.md](../../docs/chapter-development.md) |

## 為什麼要分兩邊

- **`story/`** 是創作流，文字為主，人類為主要讀者
- **`game/src/chapters/`** 是實作流，Godot 資源為主，引擎為主要讀者
- 用同一 slug 串起來，互相 grep 找得到

## 新增章節

複製現有資料夾結構：
```bash
mkdir -p story/chapters/chapter_02_market_fire
cp story/chapters/chapter_01_arrival/README.md story/chapters/chapter_02_market_fire/
# 然後開始寫 draft.md
```

Godot 端另外用 chapter_template 複製，見 [docs/chapter-development.md § 4. 新增章節流程](../../docs/chapter-development.md)。
