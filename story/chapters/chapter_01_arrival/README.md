# Chapter 1: 鐵門後的那個人

**Slug**: `chapter_01_arrival` （與 [game/src/chapters/chapter_01_arrival/](../../../game/src/chapters/chapter_01_arrival/) 對齊）

**狀態**:
- [x] 草稿（[draft.md](draft.md)）
- [ ] 抽資產清單（`assets.json` + `assets.md`，由 story-asset-extraction skill 產出）
- [ ] 美術生成（art-pipeline skill 餵 Dashboard / CLI 跑）
- [ ] Godot 端實作（場景、beats、events.gd，見 [game 對應目錄](../../../game/src/chapters/chapter_01_arrival/)）

## 一段話劇情

阿謙繼承木柵市場深處一間關了 40 年的中藥行，整理時觸發了一張舊地圖，把他穿越回 1983 年，與從未謀面的親祖父林榮昌相遇。

## 檔案

| 檔 | 用途 |
|---|---|
| [draft.md](draft.md) | 敘事草稿（劇情、角色、設定、主線） |
| `assets.json` | story-asset-extraction skill 產出的結構化資產清單（machine-readable，給 art-pipeline 餵） |
| `assets.md` | 同上的人類版鏡像（給作者審稿打勾用） |
| `notes.md`（選填） | 角色 bio、worldbuilding 補充、未來伏筆 |

## 流程提示

寫完 `draft.md` 後：
1. 叫 AI 跑 **story-asset-extraction**：「幫我從 chapter_01_arrival 的 draft 抽資產清單」
2. 確認 `assets.md` 內容（命名、姿態描述對不對）
3. 叫 AI 跑 **art-pipeline**：「把這份清單批次餵進 Dashboard」
4. 美術生完後在 Godot 端接 beats / events / npc profile（見 [docs/chapter-development.md](../../../docs/chapter-development.md)）
