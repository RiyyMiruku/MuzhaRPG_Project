# Chapter 1 — 鐵門後的那個人 · 資產清單

**來源**: [draft.md](draft.md)
**總計**: 6 moving NPCs · 6 static NPCs · 16 iso props · 6 buildings · 3 tilesets = **37 個資產**
**Chapter tag**: `1`（art-pipeline 批次跑時會套到每筆，寫進 manifest 成 `chapter:1`）

## 抽取備註

- **林榮華（= 林文彥）整章不正面登場**，只在塗黑照片、上鎖房間、未說出的名字裡存在 → **不抽 character asset**（Chapter 2 才生）
- **榮昌中藥行**分**現代（鏽鐵門、積灰）/ 1983（運作中）** 兩個 building asset，視覺差異大不適合同一個
- **醫藥櫃同理**分 `medicine_cabinet_dusty` / `medicine_cabinet_new` 兩版
- **老周**雖然「擺龍門陣」偏靜態，但 4-dir idle 用站姿較通用；搭配 `wooden_stool_old` prop 由場景擺放決定坐姿，避免 4 向坐姿違和
- **林榮華遺物**草稿說「筆記本 / 照片 / 舊鋼筆，細節待定」→ 三種都先抽出來，作者選定一個再砍其他兩個
- **阿謙母親**只接電話、未具描述 → 跳過
- **全家福另一個小孩**沒名沒對話 → 跳過
- 無人需要 idle/walk override（沒有抱嬰兒、推車、拐杖等特殊姿態）

---

## Moving NPCs (6)

| name | description（摘要） | zone | category |
|---|---|---|---|
| lin_siqian | 28 歲設計師主角，灰 T 牛仔褲帆布鞋，斜背小包 | shared | protagonist |
| lin_rongchang | 46 歲中藥行老闆，白襯衫米色圍裙，沉穩內斂 | market | shopkeeper |
| lin_ama | 72 歲曾祖母，藏青閩南上衣黑褲，銀髮髻 + 玉鐲 | market | elder_family |
| chen_xiuqin | 43 歲老闆娘，粉色花襯衫米色圍裙，務實溫和 | market | shopkeeper_family |
| lin_xiaowei | 16 歲少年，藍色校服 POLO，叛逆悶悶的 | market | teen_family |
| a_tao_yi | 55 歲菜攤阿姨，紅花襯衫草帽，市場八卦中心 | market | vendor |

## Static NPCs (6)

| name | description（摘要） | directions | zone |
|---|---|---|---|
| lao_zhou | 82 歲耆老，白髮稀疏拿摺扇，市場入口擺龍門陣 | 4 | market |
| lawyer_muzha | 60 多歲律師，深灰西裝紅領帶，圓框眼鏡 | 4 | market |
| vendor_market_oldman_01 | 60 多歲男攤販，藍襯衫鴨舌帽 | 4 | market |
| vendor_market_woman_02 | 40 多歲女攤販，格子襯衫橡膠雨鞋 + 袖套 | 4 | market |
| customer_pharmacy_woman | 50 多歲女顧客，米色襯衫深灰裙 | 4 | market |
| pedestrian_market_man | 20 多歲男路人，灰 T 牛仔褲 | 4 | market |

## Iso Props (16)

| name | description（摘要） | size | category |
|---|---|---|---|
| medicine_cabinet_dusty | 中藥多抽屜櫃，深染木積灰 40 年蛛網 | 64 | furniture |
| medicine_cabinet_new | 中藥多抽屜櫃，亮銅把手手寫紙標籤（1983 版） | 64 | furniture |
| shop_counter_wood | 中藥行櫃台，小銅秤 + 算盤 + 處方紙 | 48 | furniture |
| family_photo_blacked | **關鍵道具**：1970s 全家福，一張臉被墨水塗黑 | 24 | key_item |
| old_map_paper | **關鍵道具**：泛黃手繪木柵地圖，背面毛筆字 | 24 | key_item |
| cathay_calendar_1983 | 國泰人壽 1983 年月曆，紅字年份 | 32 | decoration |
| incense_burner_brass | 銅製三腳香爐，紅香三炷 | 24 | ritual |
| lantern_paper_red | 紅紙燈籠金穗，木樑垂掛 | 32 | decoration |
| vegetable_stall | 阿桃姨菜攤，木板櫃 + 竹簍蔬菜 + 帆布頂 | 64 | vendor_stall |
| market_basket_produce | 竹編菜籃裝地瓜青菜 | 24 | decoration |
| wooden_stool_old | 老周坐的市場小木凳 | 16 | furniture |
| id_card_old | **關鍵道具**：父親 1980s 紙本身分證（結局道具） | 16 | key_item |
| notebook_leather | **林榮華遺物候選 A**：棕色皮革小筆記本 | 24 | key_item |
| fountain_pen_old | **林榮華遺物候選 B**：黑色舊鋼筆 | 16 | key_item |
| photograph_old | **林榮華遺物候選 C**：黑白小照片 | 16 | key_item |
| iron_gate_rusted | 鏽蝕綠鐵捲門 + 大銅鎖（中藥行現代外觀關鍵） | 64 | structure |

## Buildings (6)

| name | description（摘要） | size | category |
|---|---|---|---|
| pharmacy_rongchang_modern | 中藥行現代版：鏽鐵門深鎖、招牌幾乎看不到、屋瓦長苔 | 128×128 | building |
| pharmacy_rongchang_1983 | 中藥行 1983 版：木捲門敞開、紅磚、紅燈籠、金字招牌 | 128×128 | building |
| old_apartment_muzha | 阿謙住的 4 樓老公寓，水泥外牆鐵欄陽台冷氣機 | 96×128 | building |
| law_office_muzha | 律師事務所，毛玻璃 + 金字「律師事務所」 | 96×96 | building |
| market_shophouse_minnan | 通用閩南紅磚街屋（市場其他攤位用） | 128×128 | building |
| market_shophouse_concrete | 通用戰後水泥街屋變體（市場另一種風格） | 128×128 | building |

## Tilesets (3)

| name | lower | upper | transition |
|---|---|---|---|
| market_concrete_tile | 灰水泥地磨損 | 紅方磁磚（傳統市場走道） | 水泥破口接磁磚縫 |
| courtyard_dirt_grass | 後院壓實泥地 | 雜草小野花 | 鬆土混稀疏草叢 |
| street_asphalt_sidewalk | 深灰柏油白線褪色 | 淺灰水泥人行道板 | 抬升的水泥緣石 |

---

## 下一步

1. 作者審稿：檢查角色描述、命名、zone tag、林榮華遺物三選一決定
2. 確認後叫 **art-pipeline** skill：「把 `chapter_01_arrival/assets.json` 批次餵 Dashboard」
3. Pixellab 生圖後接 Godot 端 npc profile + scene composition

確認 / 修改項目可直接編輯本檔與 `assets.json`，兩份保持同步。
