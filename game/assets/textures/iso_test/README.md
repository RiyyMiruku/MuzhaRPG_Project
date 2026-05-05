# Iso 測試素材（暫時資料夾）

> ⚠️ 僅在 `test-isometric-view` 分支使用。確認 iso 視角可行後會移到正式路徑或刪除。

## 內容

| 檔案 | 來源 | 尺寸 |
| --- | --- | --- |
| `iso_autotile_market_grass_asphalt.png` | 既有 top-down autotile 經 PIL 投影 | 128×64（4×4 cells，每 cell 32×16 菱形） |
| `iso_autotile_market_dirt_stone.png` | 同上 | 128×64 |
| `iso_autotile_riverside_water_concrete.png` | 同上 | 128×64 |
| `iso_building_shophouse.png` | Pixellab pixflux 直接生成 | 128×128 |
| `iso_building_temple.png` | 同上 | 128×128 |
| `iso_prop_market_stall.png` | 同上 | 96×96 |

## 來源管線

1. **autotile** ← `art_source/iso_pipeline/project_to_iso.py --mode cells --grid 4x4`
2. **建築 / prop** ← `art_source/iso_pipeline/generate.py`（pixellab pixflux）

詳見：[../../../../art_source/iso_pipeline/README.md](../../../../art_source/iso_pipeline/README.md)

## 在哪裡使用

[../../../src/maps/zones/zone_iso_test.tscn](../../../src/maps/zones/zone_iso_test.tscn) — 實驗場景，所有 iso 視覺驗證在此進行。
