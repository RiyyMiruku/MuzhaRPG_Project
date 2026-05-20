# Prop Horizontal Flip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a spec-driven horizontal flip toggle for objects (props/buildings), exposed as a one-click button in the asset dashboard, so Pixellab-generated lighting direction can be flipped to match scene-wide lighting without manual editing.

**Architecture:** `flip_h: bool` becomes a field in each object's `asset.json`. Pipeline's `_write_prop_tscn` emits `flip_h = true` into the Sprite2D node at import time. Dashboard remake endpoint accepts `flip_h` in overrides and re-runs only the `import_to_godot` stage (no Pixellab credits). Source PNG is never modified — spec drives visual orientation entirely at the .tscn layer.

**Tech Stack:** Python (pipeline orchestrators, FastAPI backend, pytest), TypeScript + React (dashboard frontend), Godot 4 (consumer of generated .tscn).

**Spec:** [docs/superpowers/specs/2026-05-20-prop-horizontal-flip-design.md](../specs/2026-05-20-prop-horizontal-flip-design.md)

---

## File Structure

**Created:**
- (none — feature reuses existing files)

**Modified:**
- `pipeline/orchestrators/_godot_import.py` — `import_prop()` + `_write_prop_tscn()` accept `flip_h` param; emit `flip_h = true` into Sprite2D
- `pipeline/orchestrators/prop.py` — add `--flip-h` argparse flag; upsert manifest; read final value back; pass to `import_prop()`
- `tools/asset_dashboard/backend/server.py` — `CreateAssetRequest.flip_h` + `RemakeOverrides.flip_h`; CLI args wiring; allowed-field list
- `tools/asset_dashboard/backend/manifest_io.py` — surface `flip_h` in `AssetSummary.extra`
- `tools/asset_dashboard/frontend/src/types.ts` — type annotation for `extra.flip_h` and `RemakeOverrides.flip_h`
- `tools/asset_dashboard/frontend/src/api.ts` — (no signature change; overrides field is already pass-through)
- `tools/asset_dashboard/frontend/src/components/AssetDetail.tsx` — flip toggle button (object only)

**Test files modified:**
- `tests/test_godot_import.py` — pipeline-side flip behavior
- `tools/asset_dashboard/tests/test_manifest_io.py` — flip_h projection
- `tools/asset_dashboard/tests/test_server.py` — remake override + create body

---

## Task 1: Pipeline tscn writer — bake `flip_h` into Sprite2D

**Files:**
- Modify: `pipeline/orchestrators/_godot_import.py:56-72` (`import_prop` signature), `:75-131` (`_write_prop_tscn`)
- Test: `tests/test_godot_import.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_godot_import.py`:

```python
from PIL import Image
from orchestrators._godot_import import _write_prop_tscn


def test_write_prop_tscn_no_flip(tmp_path):
    png = tmp_path / "x.png"
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png)
    tscn = tmp_path / "x.tscn"
    _write_prop_tscn(
        tscn, png, "x",
        collision="bottom_16x16", has_collision=True,
        flip_h=False,
        root=tmp_path,
    )
    text = tscn.read_text(encoding="utf-8")
    assert "flip_h" not in text  # default off → omit the line entirely


def test_write_prop_tscn_with_flip(tmp_path):
    png = tmp_path / "y.png"
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(png)
    tscn = tmp_path / "y.tscn"
    _write_prop_tscn(
        tscn, png, "y",
        collision="bottom_16x16", has_collision=True,
        flip_h=True,
        root=tmp_path,
    )
    text = tscn.read_text(encoding="utf-8")
    assert "flip_h = true" in text
    # ensure it lands inside the Sprite2D node, not floating elsewhere
    sprite_block_start = text.index('[node name="Sprite2D"')
    next_node_start = text.index("[node", sprite_block_start + 1)
    sprite_block = text[sprite_block_start:next_node_start]
    assert "flip_h = true" in sprite_block
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_godot_import.py::test_write_prop_tscn_with_flip -v
```
Expected: FAIL with `TypeError: _write_prop_tscn() got an unexpected keyword argument 'flip_h'`

- [ ] **Step 3: Add `flip_h` param to `import_prop` and `_write_prop_tscn`**

In `pipeline/orchestrators/_godot_import.py`, change the two signatures and propagate:

```python
def import_prop(
    src_png: Path, name: str, collision: str, has_collision: bool,
    *, root: Path | None = None, flip_h: bool = False,
) -> tuple[Path, Path]:
    """Copy prop PNG into Godot tree and generate a .tscn from PropTemplate.

    Returns (game_png_path, game_tscn_path), both absolute.
    """
    root = root or project_root()
    png_dest = root / "game" / "assets" / "textures" / "props" / f"{name}.png"
    tscn_dest = root / "game" / "src" / "maps" / "props" / f"{name}.tscn"
    png_dest.parent.mkdir(parents=True, exist_ok=True)
    tscn_dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(src_png, png_dest)
    _write_prop_tscn(
        tscn_dest, png_dest, name, collision, has_collision,
        flip_h=flip_h, root=root,
    )
    return png_dest, tscn_dest


def _write_prop_tscn(
    tscn_path: Path, png_path: Path, name: str, collision: str, has_collision: bool,
    *, root: Path, flip_h: bool = False,
) -> None:
```

Then locate the Sprite2D `parts.append(...)` call (currently writes `texture` and `offset`) and append a `flip_h = true` line conditionally:

```python
    sprite_lines = [
        f'[node name="Sprite2D" parent="." index="0"]',
        f'texture = ExtResource("3_tex")',
        f'offset = Vector2(0, {-h / 2.0})',
    ]
    if flip_h:
        sprite_lines.append('flip_h = true')
    parts.append("\n".join(sprite_lines) + "\n")
```

This replaces the existing single-string `parts.append('[node name="Sprite2D" ...')` block — make sure the old block is fully removed.

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tests/test_godot_import.py -v
```
Expected: ALL PASS (including the two new ones and the existing UID/collision tests).

- [ ] **Step 5: Commit**

```
git add pipeline/orchestrators/_godot_import.py tests/test_godot_import.py
git commit -m "feat(pipeline): _write_prop_tscn supports flip_h param"
```

---

## Task 2: Orchestrator CLI — `--flip-h` flag in `prop.py`

**Files:**
- Modify: `pipeline/orchestrators/prop.py:47-78` (argparse), `:160-218` (main / import wiring)
- Test: manual (no orchestrator-level integration test exists)

- [ ] **Step 1: Add the argparse flag**

In `pipeline/orchestrators/prop.py:parse_args()`, after the `--no-collision` flag, add:

```python
    p.add_argument(
        "--flip-h",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="水平翻轉 Sprite2D（解光照方向不一致）；不指定 = 沿用 manifest 既有值",
    )
```

Note: `BooleanOptionalAction` automatically provides `--no-flip-h` as the negation.

- [ ] **Step 2: Wire flip_h through main flow**

In `prop.py:main()`, locate the section that constructs the tag list (after `manifest.validate_asset_name(args.name)`). Add manifest upsert for `flip_h` BEFORE the `tags` block and re-read the entry to get the resolved value:

```python
    # Persist explicit flip_h into manifest (None = caller didn't specify; leave entry alone).
    if args.flip_h is not None:
        if manifest.get_object(ctx.name) is None:
            manifest.upsert_object(name=ctx.name, fields={"status": "init"})
        manifest.upsert_object(name=ctx.name, fields={"flip_h": bool(args.flip_h)})

    entry = manifest.get_object(ctx.name) or {}
    resolved_flip_h: bool = bool(entry.get("flip_h", False))
```

Then locate the call to `import_prop(...)` (inside the `import_to_godot` stage function). Pass `flip_h=resolved_flip_h`. Note: the stage function lives in `_common.py` framework — actually the `@stage("import_to_godot")` decorator wraps a function in this file. Find that function (named `import_to_godot` in this file) and update it:

```python
@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    src_png = manifest.object_dir(ctx.name) / f"{ctx.name}.png"
    entry = manifest.get_object(ctx.name) or {}
    flip_h = bool(entry.get("flip_h", False))
    has_coll = not args.no_collision
    game_png, game_tscn = import_prop(
        src_png, ctx.name,
        collision=args.collision,
        has_collision=has_coll,
        flip_h=flip_h,
    )
    ...
```

Read the existing `import_to_godot` function first to preserve its exact return / manifest-write logic; only change the `import_prop` call and add the `entry`/`flip_h` lookup.

- [ ] **Step 3: Verify CLI help works**

```
uv run python pipeline/orchestrators/prop.py --help
```
Expected output includes:
```
--flip-h, --no-flip-h
                      水平翻轉 Sprite2D...
```

- [ ] **Step 4: Smoke test with an existing prop**

Pick a small existing iso_prop (e.g. `lantern_paper_red`):

```
uv run python pipeline/orchestrators/prop.py \
  --name lantern_paper_red --kind iso_prop \
  --resume-from import_to_godot --force-restart-stage import_to_godot \
  --review-mode none --flip-h
```

Then check the result:

```
grep "flip_h" game/src/maps/props/lantern_paper_red.tscn
```
Expected: `flip_h = true`

Also check manifest:

```
grep "flip_h" art_source/objects/lantern_paper_red/asset.json
```
Expected: `"flip_h": true,`

Then unflip:

```
uv run python pipeline/orchestrators/prop.py \
  --name lantern_paper_red --kind iso_prop \
  --resume-from import_to_godot --force-restart-stage import_to_godot \
  --review-mode none --no-flip-h
```

`grep flip_h` on the tscn should now find nothing.

- [ ] **Step 5: Commit**

```
git add pipeline/orchestrators/prop.py
git commit -m "feat(pipeline): prop.py --flip-h / --no-flip-h CLI flag"
```

---

## Task 3: Backend models — accept `flip_h` in create + remake overrides

**Files:**
- Modify: `tools/asset_dashboard/backend/server.py:198-249` (`RemakeOverrides`, `CreateAssetRequest`), `:266-298` (override application), `:643-733` (`create_asset`)
- Test: `tools/asset_dashboard/tests/test_server.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tools/asset_dashboard/tests/test_server.py`:

```python
def test_remake_overrides_accepts_flip_h():
    from tools.asset_dashboard.backend.server import RemakeOverrides
    ov = RemakeOverrides(flip_h=True)
    assert ov.flip_h is True

def test_create_request_accepts_flip_h():
    from tools.asset_dashboard.backend.server import CreateAssetRequest
    body = CreateAssetRequest(
        asset_type="object", kind="iso_prop", name="x",
        description="a thing", flip_h=True,
    )
    assert body.flip_h is True
```

- [ ] **Step 2: Run tests to verify failure**

```
uv run pytest tools/asset_dashboard/tests/test_server.py::test_remake_overrides_accepts_flip_h tools/asset_dashboard/tests/test_server.py::test_create_request_accepts_flip_h -v
```
Expected: FAIL with `pydantic.ValidationError: ... flip_h ... Extra inputs are not permitted` (since pydantic by default rejects unknown fields).

- [ ] **Step 3: Add `flip_h` to both models**

In `tools/asset_dashboard/backend/server.py`, modify `RemakeOverrides`:

```python
class RemakeOverrides(BaseModel):
    """Spec fields the caller wants to change before re-running the stage.
    Any field present is upserted into the manifest entry before subprocess
    spawn — the orchestrator then reads the new spec naturally on startup."""
    kind: str | None = None
    description: str | None = None
    view: str | None = None
    width: int | None = None
    height: int | None = None
    size: int | None = None
    collision: str | None = None
    flip_h: bool | None = None
```

Modify `CreateAssetRequest` — add right after the `chapter` field:

```python
    flip_h: bool | None = None
```

- [ ] **Step 4: Add `flip_h` to the override-allowed list and CLI wiring**

In `remake()` (around `server.py:276`), extend the object-bucket fields tuple:

```python
        elif asset_type == "object":
            fields: dict = {}
            for k in ("kind", "description", "view", "collision", "flip_h"):
                if k in ov:
                    fields[k] = ov[k]
```

Then in the cmd-assembly section for `asset_type == "object"` (around `server.py:309-334`), after the existing `size` handling, add:

```python
        flip_h_val = entry.get("flip_h")
        if isinstance(flip_h_val, bool):
            cmd += ["--flip-h" if flip_h_val else "--no-flip-h"]
```

In `create_asset()` (around `server.py:722-728`), after the chapter wiring, add:

```python
    if body.flip_h is not None:
        cli_args += ["--flip-h" if body.flip_h else "--no-flip-h"]
```

- [ ] **Step 5: Run tests to verify pass**

```
uv run pytest tools/asset_dashboard/tests/test_server.py -v
```
Expected: PASS (both new tests, and no regression elsewhere).

- [ ] **Step 6: Commit**

```
git add tools/asset_dashboard/backend/server.py tools/asset_dashboard/tests/test_server.py
git commit -m "feat(dashboard): backend accepts flip_h in create + remake overrides"
```

---

## Task 4: Backend manifest projection — surface `flip_h` in `AssetSummary.extra`

**Files:**
- Modify: `tools/asset_dashboard/backend/manifest_io.py:131-148`
- Test: `tools/asset_dashboard/tests/test_manifest_io.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tools/asset_dashboard/tests/test_manifest_io.py`:

```python
def test_load_assets_surfaces_flip_h(tmp_path):
    mpath = tmp_path / "manifest.json"
    mpath.write_text(json.dumps({
        "characters": {},
        "tilesets": {},
        "objects": {
            "lantern": {
                "description": "red lantern",
                "tags": ["zone:zone_market_1983"],
                "stages": {},
                "kind": "iso_prop",
                "flip_h": True,
            },
            "stool": {
                "description": "wooden stool",
                "tags": [],
                "stages": {},
                "kind": "iso_prop",
                # no flip_h field at all
            },
        },
    }), encoding="utf-8")
    assets = {a.name: a for a in load_assets(mpath)}
    assert assets["lantern"].extra["flip_h"] is True
    assert assets["stool"].extra["flip_h"] is False
```

- [ ] **Step 2: Run test to verify failure**

```
uv run pytest tools/asset_dashboard/tests/test_manifest_io.py::test_load_assets_surfaces_flip_h -v
```
Expected: FAIL with `KeyError: 'flip_h'`.

- [ ] **Step 3: Add `flip_h` to extra**

In `tools/asset_dashboard/backend/manifest_io.py:load_assets()`, locate the `extra={...}` block (around line 143) and add `flip_h`:

```python
                extra={
                    "character_id": entry.get("character_id"),
                    "directions": entry.get("directions"),
                    "kind": entry.get("kind"),
                    "flip_h": bool(entry.get("flip_h", False)),
                },
```

- [ ] **Step 4: Run tests to verify pass**

```
uv run pytest tools/asset_dashboard/tests/test_manifest_io.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add tools/asset_dashboard/backend/manifest_io.py tools/asset_dashboard/tests/test_manifest_io.py
git commit -m "feat(dashboard): expose flip_h in AssetSummary.extra"
```

---

## Task 5: Frontend types — declare `flip_h` shape

**Files:**
- Modify: `tools/asset_dashboard/frontend/src/types.ts`

- [ ] **Step 1: Add `flip_h` typing**

The frontend already declares `extra: Record<string, unknown>` and `CreateAssetBody` is open-ended. Make `flip_h` explicit so the toggle code has a real type:

Locate `AssetSummary.extra` (currently `extra: Record<string, unknown>`). Replace with a structured shape:

```typescript
export interface AssetSummary {
  // ... existing fields unchanged ...
  extra: {
    character_id?: string | null
    directions?: number | null
    kind?: string | null
    flip_h?: boolean
    [k: string]: unknown
  }
}
```

(Keep the `[k: string]: unknown` index signature so it stays open for future fields.)

In `CreateAssetBody`, add the field after `chapter?`:

```typescript
  flip_h?: boolean
```

Find or add a `RemakeOverrides` type if one exists (search for `RemakeOverrides` first). If not, add it:

```typescript
export interface RemakeOverrides {
  kind?: string
  description?: string
  view?: string
  width?: number
  height?: number
  size?: number
  collision?: string
  flip_h?: boolean
}

export interface RemakeBody {
  stage: string
  prompt?: string
  directions?: string[]
  overrides?: RemakeOverrides
}
```

If `RemakeBody` already exists, just add the `flip_h?: boolean` field to its overrides shape.

- [ ] **Step 2: Verify types compile**

```
cd tools/asset_dashboard/frontend && pnpm exec tsc --noEmit
```
Expected: exit 0, no errors.

- [ ] **Step 3: Commit**

```
git add tools/asset_dashboard/frontend/src/types.ts
git commit -m "feat(dashboard): frontend types for flip_h"
```

---

## Task 6: Frontend `api.ts` — ensure remake passes overrides through

**Files:**
- Modify: `tools/asset_dashboard/frontend/src/api.ts` (only if remake API doesn't already accept `overrides`)

- [ ] **Step 1: Read the existing api.ts to confirm remake signature**

```
grep -n "remake" tools/asset_dashboard/frontend/src/api.ts
```

If the remake function already takes a generic body parameter that passes through to fetch (e.g. `remake(type, name, body)`), no change needed — skip to Step 3.

If it has a narrow signature like `remake(type, name, stage, prompt?)`, widen it:

```typescript
import type { RemakeBody } from "./types"

export const api = {
  // ...
  async remake(assetType: AssetType, name: string, body: RemakeBody): Promise<{ job_id: string; stage: string }> {
    const r = await fetch(`/api/asset/${assetType}/${encodeURIComponent(name)}/remake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error(`remake failed: ${r.status} ${await r.text()}`)
    return r.json()
  },
}
```

Adjust to match the file's existing patterns (some files use a class, some use a plain object). Preserve whatever else is there.

- [ ] **Step 2: Verify types compile**

```
cd tools/asset_dashboard/frontend && pnpm exec tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 3: Commit (only if step 1 modified the file)**

```
git add tools/asset_dashboard/frontend/src/api.ts
git commit -m "feat(dashboard): frontend remake API accepts overrides"
```

If no change was needed, skip the commit.

---

## Task 7: Frontend toggle button in `AssetDetail.tsx`

**Files:**
- Modify: `tools/asset_dashboard/frontend/src/components/AssetDetail.tsx`

- [ ] **Step 1: Add the flip button next to existing actions**

Read the current button-row area (search for "Delete" — that's the closest neighbour). Insert a new conditional button visible only for object-type assets.

Around the existing button group (look for `<button` near "Delete"), add:

```tsx
{asset.asset_type === "object" && (
  <button
    type="button"
    onClick={async () => {
      const newVal = !asset.extra.flip_h
      try {
        await api.remake(asset.asset_type, asset.name, {
          stage: "import_to_godot",
          overrides: { flip_h: newVal },
        })
      } catch (e) {
        window.alert(`Flip failed: ${(e as Error).message}`)
      }
    }}
    className="rounded bg-stone-700 px-3 py-1.5 text-sm hover:bg-stone-600"
    title="Toggle Sprite2D.flip_h — re-runs import_to_godot stage (no Pixellab credits)"
  >
    {asset.extra.flip_h ? "Unflip horizontal" : "Flip horizontal"}
  </button>
)}
```

If `api` isn't imported in the file already, add the import at the top:

```tsx
import { api } from "../api"
```

- [ ] **Step 2: Verify types compile**

```
cd tools/asset_dashboard/frontend && pnpm exec tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 3: Commit**

```
git add tools/asset_dashboard/frontend/src/components/AssetDetail.tsx
git commit -m "feat(dashboard): flip horizontal toggle in AssetDetail"
```

---

## Task 8: End-to-end manual validation

**Files:** (none modified — verification only)

- [ ] **Step 1: Rebuild frontend**

```
cd tools/asset_dashboard/frontend && pnpm build
```
Expected: exit 0.

- [ ] **Step 2: Start backend**

```
uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765
```

Open http://localhost:8765/ in a browser.

- [ ] **Step 3: Toggle flip on a real prop**

1. Pick an object (e.g. `lantern_paper_red`)
2. Click into its detail page
3. Note current sprite orientation (or thumbnail in list)
4. Click **Flip horizontal**
5. Wait for the job log panel to show `import_to_godot` job completed
6. Refresh the page or open the asset again — thumbnail should be mirrored
7. Verify on disk:
   ```
   grep flip_h art_source/objects/lantern_paper_red/asset.json
   grep flip_h game/src/maps/props/lantern_paper_red.tscn
   ```
   Both should show `flip_h: true` / `flip_h = true`.

- [ ] **Step 4: Verify in Godot editor**

1. Open `game/src/maps/props/lantern_paper_red.tscn` in Godot
2. Select Sprite2D
3. Inspector → Animation section → `Flip H` checkbox should be ✓
4. Viewport sprite shows mirrored.

- [ ] **Step 5: Toggle off**

Back to dashboard, click **Unflip horizontal**. Wait for job, verify:
- Manifest no longer has `"flip_h": true` (or has `false`)
- tscn no longer contains the `flip_h = true` line
- Godot viewport reverts to original orientation.

- [ ] **Step 6: Verify Pixellab remake preserves spec**

With `flip_h: true` set on a prop, trigger a Pixellab regen via dashboard Remake on `generate_object` stage. After the full pipeline re-runs, the resulting tscn should still have `flip_h = true` (spec is the SSOT).

- [ ] **Step 7: Final commit (if any straggling fixes)**

```
git status
```

If everything is committed and clean, skip. Otherwise commit the loose ends with a descriptive message.

---

## Self-Review Notes

- **Spec coverage**: All 6 sections of design spec map to a task (spec field ↔ Task 2+3, orchestrator ↔ Task 2, pipeline writer ↔ Task 1, backend ↔ Task 3+4, frontend ↔ Task 5+6+7, no-backfill ↔ implicit by design).
- **Test coverage**: pipeline writer (Task 1), backend models (Task 3), manifest projection (Task 4). Frontend has tsc check only — no React testing infra exists in this repo.
- **Names consistent**: `flip_h` snake_case in Python/manifest/CLI; `flip_h` also in TS (matches JSON field). No camelCase conversion.
- **Order**: dependencies flow Task 1 (pipeline) → Task 2 (CLI consumes pipeline) → Task 3 (backend calls CLI) → Task 4 (backend exposes data) → Task 5 (frontend types) → Task 6 (frontend API) → Task 7 (frontend UI uses API). Task 8 validates end-to-end.
- **YAGNI hold**: no vertical flip, no character flip, no batch flip — all explicitly out of scope per spec.
