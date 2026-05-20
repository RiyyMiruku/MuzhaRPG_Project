# Prop Horizontal Flip — Design

> **狀態**：approved 2026-05-20
> **範圍**：dashboard 加一鍵左右翻轉 prop / building 的功能，解決 Pixellab 生成圖光照方向跟場景不一致的問題。

## 動機

Pixellab 對單一 prop / building 的生成圖光照方向是隨機的（通常從某一側打光）。當這些 prop 擺進 iso 場景時，整體場景需要統一光源方向，常常需要把某些 prop 左右翻轉才能跟其他元素的光照一致。

目前要做這件事只能：

- 手動在 Godot inspector 對 Sprite2D 設 `flip_h = true`（per-instance，麻煩，且 prop 多 instance 時要重複設）
- 或編輯 PNG 鏡像（破壞性，re-generate 後失效，且 spec ↔ artifact drift）

需要一個 **spec-driven 的翻轉機制**：宣告在 asset spec 上，pipeline 自動寫進 .tscn，re-generate 不掉。

## 範圍

| Asset type | 支援 flip? | 原因 |
|---|---|---|
| object (iso_prop / building / iso_building) | ✅ | 此 spec 的目標 |
| character | ❌ | 8-direction rotations 系統會被翻轉破壞語義 |
| tileset | ❌ | Wang 16-cell 是對稱的，且 TileMapDual 自動處理朝向 |

**只做左右翻**。垂直翻轉 / 任意旋轉 / 批次翻轉同 zone 所有 prop 都不在範圍內。

## 架構

```
asset.json `flip_h: true`        ← spec / SSOT
        │
        ▼
prop.py orchestrator
        │ (--flip-h flag 或從 manifest 讀)
        ▼
_write_prop_tscn 寫入 Sprite2D.flip_h     ← runtime visual
        │
        ▼
.tscn 在 editor / runtime 都顯示翻轉的圖
```

碰撞框不翻：碰撞跟光照無關，現有 collision rect 永遠對稱（bottom-anchor + horizontal-center），翻轉視覺不影響碰撞行為。

## 改動清單

### 1. Spec 層：`asset.json` 加 `flip_h: bool`

預設 `false`。缺欄位視為 false。

```json
{
  "kind": "iso_prop",
  "description": "...",
  "size": {"width": 32, "height": 32},
  "flip_h": true
}
```

### 2. Orchestrator CLI：`pipeline/orchestrators/prop.py`

新增 flag：

```
--flip-h              將生成的 prop 在 Godot 端水平翻轉
--no-flip-h           明確標記不翻（覆蓋 manifest 既有值）
```

argparse pattern：用 `argparse.BooleanOptionalAction`（單一 `--flip-h` 自動產出 `--no-flip-h` 反義 flag）。`default=None` 區分「沒指定」vs「明確 false」——只有非 None 才 upsert 進 manifest，避免每次 resume 都覆寫使用者的 toggle。

在 `import_to_godot` stage 前（或於 main 函式）：
- 讀 args.flip_h（可能是 None）
- 若非 None，upsert_object(name, fields={"flip_h": args.flip_h})
- 從 manifest entry 讀最終 `flip_h`（None / 缺 → false）
- 傳給 `import_prop()` / `_write_prop_tscn()`

### 3. Pipeline tscn writer：`pipeline/orchestrators/_godot_import.py`

`import_prop()` 與 `_write_prop_tscn()` 新增 `flip_h: bool = False` 參數。

Sprite2D 段落改為：

```python
sprite_lines = [
    '[node name="Sprite2D" parent="." index="0"]',
    'texture = ExtResource("3_tex")',
    f'offset = Vector2(0, {-h / 2.0})',
]
if flip_h:
    sprite_lines.append('flip_h = true')
parts.append("\n".join(sprite_lines) + "\n")
```

不動碰撞框、不動 InteractArea。

### 4. Dashboard backend：`tools/asset_dashboard/backend/server.py`

**`CreateAssetRequest`** 加：
```python
flip_h: bool | None = None
```
若非 None，CLI 組裝時加 `--flip-h` 或 `--no-flip-h`。

**`RemakeOverrides`** 加：
```python
flip_h: bool | None = None
```
在 object override 的允許欄位 list 加上 `"flip_h"`：
```python
for k in ("kind", "description", "view", "collision", "flip_h"):
    ...
```

**`manifest_io.AssetSummary.extra`** 增加 `flip_h` 欄位：
```python
extra={
    "character_id": entry.get("character_id"),
    "directions": entry.get("directions"),
    "kind": entry.get("kind"),
    "flip_h": entry.get("flip_h", False),
},
```

### 5. Dashboard frontend：`tools/asset_dashboard/frontend/src/components/AssetDetail.tsx`

只對 object 顯示。在 Delete 按鈕附近加：

```tsx
{asset.asset_type === "object" && (
  <button onClick={async () => {
    const newVal = !(asset.extra.flip_h as boolean)
    await api.remake(asset.asset_type, asset.name, {
      stage: "import_to_godot",
      overrides: { flip_h: newVal },
    })
  }}>
    {asset.extra.flip_h ? "Unflip" : "Flip horizontal"}
  </button>
)}
```

`types.ts` 對應加 `extra.flip_h` 型別 / `RemakeBody.overrides.flip_h`。

### 6. 既有 25 個 object：不回灌

asset.json 沒 `flip_h` 欄位 = false，沒副作用。要翻的個別處理。

## 互動行為

| 動作 | 結果 |
|---|---|
| 新建 prop 時勾 flip | spec 寫 `flip_h: true`，初始 import 就翻 |
| 已存在 prop 按 dashboard Flip | spec 更新 + remake `import_to_godot` stage（秒級，不打 Pixellab） |
| Pixellab remake `generate_object` 整支重生 | spec `flip_h` 保留，最終 import 時還是翻 |
| CLI 手動 `--flip-h` resume `import_to_godot` | 同 dashboard flip |
| `--no-flip-h` resume | spec 寫 `false`，import 不翻 |
| Dashboard 沒有按 flip / CLI 沒帶 flag | spec 不變動，沿用既有值 |

## 邊界情況

- **carbon-copy 失效**：若 prop 在某個 zone 已被 instance 化且 inspector 手動加了 `flip_h`，spec 改 flip 後該 instance 變雙重翻轉（取消效果）。**接受這個風險**：use case 是「先決定 prop 的 canonical flip 再放進場景」，不是「先放再翻」。
- **PropTemplate 修改**：Sprite2D `flip_h` 是 instance override，PropTemplate 自己不設 `flip_h`，所以個別 prop tscn 翻轉跟 template 不衝突。
- **碰撞語義**：collision rect 永遠 bottom-anchored + horizontal-symmetric，翻轉視覺後碰撞行為不變。若未來有非對稱碰撞需求，另開 spec 處理。

## 不做

- 垂直翻轉（光照問題主要是左右）
- 任意旋轉
- Character / tileset 的 flip
- 整 zone 批次翻轉
- Flip preview（dashboard 可以靠重新拉 thumbnail 觀察）

## 測試

- Backend unit test：`load_assets` 對有 `flip_h` 欄位的 entry 正確投影到 extra
- Backend integration：POST `/api/asset/object/X/remake` body `overrides.flip_h: true` 後，manifest entry 確實有 `flip_h: true`，且 CLI subprocess 跑 `--flip-h`
- Pipeline：對一個 fixture PNG 跑 `_write_prop_tscn(flip_h=True)`，verify 產出的 tscn 含 `flip_h = true` 一行
- 手動驗證：dashboard 點 flip，開 Godot 看 prop tscn 的 Sprite2D inspector 顯示 flip_h=on，editor + runtime 視覺都翻

## 工時

- spec + orchestrator: 1 hr
- backend: 30 min
- frontend: 30 min
- 測試 + 驗證: 30 min
- **總計 ~2.5 hr**

## 相關
- [art-pipeline skill](../../.claude/skills/art-pipeline/SKILL.md)
- [_godot_import.py](../../pipeline/orchestrators/_godot_import.py)
- [Prop.gd](../../game/src/maps/props/Prop.gd)
