# Asset Naming Convention

Project-wide rules for naming art-pipeline assets (manifest keys). Enforced by
`manifest.validate_asset_name()`; orchestrators reject invalid names before any
Pixellab call.

## Hard rules (regex-enforced)

```
^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$    length 3–64
```

- Lowercase ASCII letters, digits, underscores only
- Must start with a letter, end with a letter or digit
- No consecutive underscores (`__`)
- No hyphens, spaces, dots, uppercase, or non-ASCII

Invalid examples: `Chen_ayi`, `_leading`, `trailing_`, `double__under`, `ab`,
`with-dash`, `123start`, `中文名`.

## Recommended structure per asset type

### Characters

- **Named NPC** — `<surname>_<given>`
  - `chen_ayi`, `lin_zhiwei`
- **Role-based / generic NPC** — `<role>_<location>_<NN>`
  - `vendor_market_01`, `student_nccu_03`
- **Player variants** — `player_<class>`
  - `player_default`, `player_alt`

### Tilesets

- `<zone>_<lower>_<upper>`
  - `market_grass_asphalt`, `riverside_water_sand`

### Buildings (`prop.py --kind=building`)

- `<zone>_<type>[_NN]`
  - `nccu_dormitory`, `market_shophouse_01`
  - Note: zone prefix here is descriptive — the `--zone` tag is the canonical
    filter, not the name prefix. (e.g. `muzha_shophouse_01` is fine as a name
    even though the zone tag is `market`.)

### Iso props (`prop.py --kind=iso_prop`)

- `<category>_<descriptor>`
  - `lantern_red`, `cart_fruit`, `sign_market`

## Tags vs name

- **Name** is the manifest's unique key. Keep it short and stable; renaming
  costs (it changes the manifest key + output directory).
- **Zone / category** are written into `entry.tags` via `--zone <z>` and
  `--category <c>` orchestrator flags. They live separately from the name so:
  - Renaming or re-tagging is zero-cost (just rewrites the tag list).
  - One asset can belong to multiple zones (`zone:market`, `zone:shared`).
  - Filtering is uniform across asset types.
- Do **not** duplicate zone/category info inside the name. Pick one structure
  pattern from above and let tags carry the metadata.

## Canonical zones

Defined in `pipeline/zones.py`:

```
market, nccu, riverside, zhinan, shared, test
```

`shared` = cross-zone reusable assets. `test` = experimental / throwaway.

## Example queries

```powershell
# All assets in the market zone
uv run python pipeline/orchestrators/list_assets.py --zone market

# All vendor NPCs across zones
uv run python pipeline/orchestrators/list_assets.py `
  --type character --category vendor

# Tilesets in market zone
uv run python pipeline/orchestrators/list_assets.py `
  --type tileset --zone market

# Free-form tag filter (AND logic, repeatable)
uv run python pipeline/orchestrators/list_assets.py `
  --tag zone:market --tag category:decoration
```

## Migration

Existing manifest entries without `tags` keep working — `add_tags()` lazily
creates the field. To back-fill, either re-run an orchestrator with `--zone`
/ `--category`, or call `manifest.add_tags(...)` directly from a one-off
script.
