import { useEffect, useState } from "react"
import { Check, Circle, ImageOff, Play, RotateCcw, Pencil } from "lucide-react"
import type { AssetSummary, StageDetail, StageImage, StageFrameInfo } from "../types"
import { api } from "../api"
import { PromptEditor } from "./PromptEditor"
import { PixelEditor } from "./PixelEditor"

/** Stages that send a user-authored prompt to Pixellab — show editable
 *  textarea + submit. Local-processing stages (chroma_key / iso_project /
 *  verify_in_godot / compile_spritesheet / import_to_godot) fall through to
 *  NoPromptRemake (plain re-run button). */
const PROMPT_STAGES = new Set<string>([
  "generate_8dir_base",
  "generate_4dir_base",
  "generate_object",
  "generate_atlas",
  // v2:
  "generate_rotations",
])

/** Animation stages — both v1 and v2 paths now call Pixellab in TEMPLATE mode
 *  (skeleton-driven, no action_description). Prompts in the manifest for
 *  add_*_animation are leftover from the pre-template era and ignored. UI
 *  shows a button + direction picker + confirm, no textarea. */
const TEMPLATE_ANIM_STAGES = new Set<string>([
  "add_idle_animation",
  "add_walk_animation",
  "animate_idle",
  "animate_walk",
])

const TEMPLATE_ANIM_LABELS: Record<string, string> = {
  add_idle_animation: "breathing-idle template (legacy v1 pipeline)",
  add_walk_animation: "walking-N-frames template (legacy v1 pipeline)",
  animate_idle: "breathing-idle template",
  animate_walk: "walking-6-frames template",
}

const TEMPLATE_ANIM_DIRECTIONS: Record<string, string[]> = {
  add_idle_animation: ["south", "east", "north", "west"],
  add_walk_animation: [
    "south", "east", "north", "west",
    "south-east", "north-east", "north-west", "south-west",
  ],
  animate_idle: ["south", "east", "north", "west"],
  animate_walk: [
    "south", "east", "north", "west",
    "south-east", "north-east", "north-west", "south-west",
  ],
}

interface Props {
  asset: AssetSummary
  stage: string
  realized: boolean
  /** Bumps when a remake/submit happens elsewhere, forces refetch. */
  refreshKey?: number
  /** Called after a pixel-editor save so the parent can bump refreshKey,
   *  cascading a refetch of stage detail + AssetPreview. */
  onPixelSaved?: () => void
}

export function StageSection({ asset, stage, realized, refreshKey, onPixelSaved }: Props) {
  const [detail, setDetail] = useState<StageDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .stage(asset.asset_type, asset.name, stage)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message)
      })
    return () => {
      cancelled = true
    }
  }, [asset.asset_type, asset.name, stage, refreshKey])

  const initialPrompt =
    detail?.prompt ??
    asset.prompts[stage] ??
    (stage.startsWith("generate_") ? asset.description ?? "" : "")

  const hasPrompt = PROMPT_STAGES.has(stage)
  const isTemplateAnim = TEMPLATE_ANIM_STAGES.has(stage)

  return (
    <section className="rounded-lg border border-stone-800 bg-stone-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          {realized ? (
            <Check className="h-4 w-4 text-emerald-400" />
          ) : (
            <Circle className="h-4 w-4 text-stone-600" />
          )}
          <span
            className={
              "font-mono " + (realized ? "text-stone-200" : "text-stone-500")
            }
          >
            {stage}
          </span>
        </div>
        {detail?.completed_at && (
          <span className="text-xs text-stone-500">{detail.completed_at}</span>
        )}
      </div>

      {error && (
        <p className="mb-2 text-xs text-red-400">stage load failed: {error}</p>
      )}

      {detail && detail.images.length > 0 && (
        <StageImageStrip images={detail.images} onPixelSaved={onPixelSaved} />
      )}

      {asset.asset_type === "object" && stage === "generate_object" && (
        <ObjectKindOverride asset={asset} />
      )}

      {hasPrompt ? (
        <PromptEditor
          asset={asset}
          stage={stage}
          initialPrompt={initialPrompt}
          realized={realized}
        />
      ) : isTemplateAnim ? (
        <TemplateAnimRemake asset={asset} stage={stage} realized={realized} />
      ) : (
        <NoPromptRemake asset={asset} stage={stage} realized={realized} />
      )}
    </section>
  )
}

interface NoPromptProps {
  asset: AssetSummary
  stage: string
  realized: boolean
}

/** Non-Pixellab stage — show only a plain re-run button when already realized.
 *  Pure local processing (no prompt), so no textarea is shown. */
function NoPromptRemake({ asset, stage, realized }: NoPromptProps) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const runStage = async (confirmMsg: string) => {
    if (!window.confirm(confirmMsg)) return
    setBusy(true)
    setErr(null)
    try {
      await api.remake(asset.asset_type, asset.name, stage)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!realized) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-stone-500">
          本階段是本地處理(不送 Pixellab)。通常前一階段完成後會自動跑;
          若卡住,可手動觸發(會 resume-from 此 stage,接著一路跑到 pipeline 結束)。
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() =>
              runStage(
                `Run stage "${stage}" 並繼續跑後續 stage? 本地處理,不會花 Pixellab credit。`
              )
            }
            disabled={busy}
            className="flex items-center gap-1 rounded bg-emerald-900/60 px-2 py-1 text-xs hover:bg-emerald-800 disabled:bg-stone-700 disabled:text-stone-500"
          >
            <Play className="h-3 w-3" />
            {busy ? "Running…" : "Run this stage"}
          </button>
          {err && <span className="text-xs text-red-400">{err}</span>}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() =>
          runStage(
            `Re-run stage "${stage}"? 本地處理,不會花 Pixellab credit。下游 stage 不會自動失效,需要分別 re-run。`
          )
        }
        disabled={busy}
        className="flex items-center gap-1 rounded bg-stone-800 px-2 py-1 text-xs hover:bg-stone-700 disabled:bg-stone-700 disabled:text-stone-500"
      >
        <RotateCcw className="h-3 w-3" />
        {busy ? "Running…" : "Re-run this stage"}
      </button>
      {err && <span className="text-xs text-red-400">{err}</span>}
    </div>
  )
}

interface TemplateAnimProps {
  asset: AssetSummary
  stage: string
  realized: boolean
}

/** Template-driven animation stage — no prompt, just a directions picker +
 *  Remake button. Both v1 (add_idle/walk_animation) and v2 (animate_idle/walk)
 *  call Pixellab in template mode now; the manifest prompts are ignored. */
function TemplateAnimRemake({ asset, stage, realized }: TemplateAnimProps) {
  const availableDirs = TEMPLATE_ANIM_DIRECTIONS[stage] ?? []
  const templateLabel = TEMPLATE_ANIM_LABELS[stage] ?? "Pixellab template"

  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [selectedDirs, setSelectedDirs] = useState<Set<string>>(
    () => new Set(availableDirs)
  )

  const toggleDir = (d: string) => {
    setSelectedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(d)) next.delete(d); else next.add(d)
      return next
    })
  }
  const allSelected =
    availableDirs.length > 0 && availableDirs.every((d) => selectedDirs.has(d))
  const partial = !allSelected && selectedDirs.size > 0

  const submit = async () => {
    const dirList = availableDirs.filter((d) => selectedDirs.has(d))
    if (dirList.length === 0) {
      setErr("at least one direction required")
      return
    }
    const scope = partial ? `only ${dirList.join(", ")}` : "all directions"
    if (
      !window.confirm(
        `Remake "${stage}" (${scope})?\n\n` +
        `Template: ${templateLabel}\n` +
        `Pixellab credit: ${dirList.length} direction(s) × 1 gen each.\n\n` +
        `下游 stage (compile_spritesheet / import_to_godot) 不會自動失效,需要分別 remake。`
      )
    ) return
    setBusy(true); setErr(null)
    try {
      // Pass directions only when user narrowed the set; full selection acts
      // as "regen all" (server treats undefined the same).
      const dirsToPass = partial ? dirList : undefined
      await api.remake(asset.asset_type, asset.name, stage, undefined, dirsToPass)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 rounded border border-stone-800 bg-stone-950 p-2">
      <p className="mb-2 text-xs text-stone-500">
        Template-driven stage — Pixellab uses{" "}
        <span className="font-mono text-stone-300">{templateLabel}</span>{" "}
        skeleton. 沒有 prompt 可以編輯;只能選方向 + 重生。
      </p>
      {availableDirs.length > 0 && (
        <div className="mb-2 rounded border border-stone-800 bg-stone-900 px-2 py-1.5">
          <div className="mb-1 flex items-center justify-between text-[10px]">
            <span className="text-stone-400">
              Regen directions
              {partial && <span className="ml-1 text-amber-400">(partial)</span>}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setSelectedDirs(new Set(availableDirs))}
                className="text-stone-500 hover:text-stone-300"
              >
                all
              </button>
              <button
                type="button"
                onClick={() => setSelectedDirs(new Set())}
                className="text-stone-500 hover:text-stone-300"
              >
                none
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {availableDirs.map((d) => {
              const active = selectedDirs.has(d)
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDir(d)}
                  className={
                    "rounded border px-1.5 py-0.5 text-[10px] font-mono " +
                    (active
                      ? "border-emerald-700 bg-emerald-900/40 text-emerald-100"
                      : "border-stone-700 bg-stone-950 text-stone-500 hover:border-stone-600")
                  }
                >
                  {d}
                </button>
              )
            })}
          </div>
        </div>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={busy || selectedDirs.size === 0}
          className="flex items-center gap-1 rounded bg-emerald-700 px-2 py-1 text-xs text-emerald-50 hover:bg-emerald-600 disabled:bg-stone-700 disabled:text-stone-500"
        >
          {realized ? <RotateCcw className="h-3 w-3" /> : <Play className="h-3 w-3" />}
          {busy
            ? "Submitting…"
            : realized
              ? `Remake ${partial ? `(${selectedDirs.size})` : "all"}`
              : `Run ${partial ? `(${selectedDirs.size})` : "all"}`}
        </button>
        {err && <span className="text-xs text-red-400">{err}</span>}
      </div>
    </div>
  )
}

const OBJECT_KIND_LABELS: Record<string, string> = {
  iso_prop: "Iso prop (≤64px, /create-isometric-tile)",
  iso_building: "Iso building (pixflux + isometric)",
  building: "Building (top-down, /map-objects)",
}

/** Lets the user switch an object's `kind` and regen. Calls /remake with
 *  overrides={kind} so the manifest is updated before the orchestrator
 *  reads it. The orchestrator naturally takes the new pipeline path
 *  (e.g. building → iso_building swaps the Pixellab endpoint). */
function ObjectKindOverride({ asset }: { asset: AssetSummary }) {
  const currentKind = (asset.extra?.kind as string | undefined) ?? ""
  const [picked, setPicked] = useState<string>(currentKind)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const changed = picked && picked !== currentKind

  const submit = async () => {
    if (!changed) return
    if (!window.confirm(
      `Change kind: "${currentKind}" → "${picked}"?\n\n` +
      `This will:\n` +
      `  1. Update manifest spec (kind: "${picked}")\n` +
      `  2. Re-run generate_object via the new pipeline\n` +
      `  3. chroma_key + import_to_godot will follow\n\n` +
      `Pixellab credit: 1 generation. 下游 .tscn 會自動覆蓋。`
    )) return
    setBusy(true); setErr(null)
    try {
      await api.remakeWithOverrides(
        "object", asset.name, "generate_object",
        { kind: picked },
      )
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 rounded border border-amber-900/40 bg-stone-950 p-2">
      <div className="mb-1 flex items-center justify-between text-[10px]">
        <span className="font-mono text-amber-400">spec override</span>
        <span className="text-stone-500">current: <code>{currentKind}</code></span>
      </div>
      <div className="flex items-center gap-2">
        <label className="flex-1 text-xs">
          <select
            value={picked}
            onChange={(e) => setPicked(e.target.value)}
            className="w-full rounded bg-stone-800 px-2 py-1 text-xs"
            disabled={busy}
          >
            {Object.entries(OBJECT_KIND_LABELS).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={submit}
          disabled={!changed || busy}
          className="rounded bg-amber-700 px-2 py-1 text-xs text-amber-50 hover:bg-amber-600 disabled:bg-stone-700 disabled:text-stone-500"
        >
          {busy ? "Applying…" : "Apply & Remake"}
        </button>
      </div>
      {changed && picked === "iso_building" && (
        <p className="mt-1 text-[10px] text-stone-500">
          ⚠️ iso_building 用 pixflux + weakly-guiding isometric。Description
          要帶 "isometric view, 30-degree angle, visible roof and two side walls"
          字眼,否則出立面圖。可在 PromptEditor 改完 description 再 Apply。
        </p>
      )}
      {err && <p className="mt-1 text-xs text-red-400">{err}</p>}
    </div>
  )
}

interface StripProps {
  images: StageImage[]
  onPixelSaved?: () => void
}

function StageImageStrip({ images, onPixelSaved }: StripProps) {
  // If any image has frames metadata, stack vertically (frame grids take a
  // full row). Otherwise keep the wrap-grid for square thumbs.
  const hasFrames = images.some((i) => i.frames || i.url.includes("/api/asset/sheet-row"))
  const layoutCls = hasFrames
    ? "mb-3 flex flex-col gap-1.5 rounded bg-stone-950 p-2"
    : "mb-3 flex flex-wrap gap-2 rounded bg-stone-950 p-2"
  return (
    <div className={layoutCls}>
      {images.map((img) =>
        img.frames ? (
          <FrameGrid
            key={img.path}
            info={img.frames}
            label={img.path.split("#").pop() ?? img.path}
            onPixelSaved={onPixelSaved}
          />
        ) : (
          <StageImageThumb
            key={img.path}
            url={img.url}
            path={img.path}
            onPixelSaved={onPixelSaved}
          />
        )
      )}
    </div>
  )
}

interface FrameGridProps {
  info: StageFrameInfo
  label: string
  onPixelSaved?: () => void
}

/** Renders one (action, direction) row as N clickable frame thumbnails.
 *  Click any frame to open the pixel editor scoped to that frame — saves
 *  PUT back into the sheet at the right offset. */
function FrameGrid({ info, label, onPixelSaved }: FrameGridProps) {
  // Bust caches when we edit so the thumbnail refreshes after Save.
  const [bust, setBust] = useState(0)
  const [editingCol, setEditingCol] = useState<number | null>(null)

  if (info.count <= 0) return null
  const cols: number[] = []
  for (let i = 0; i < info.count; i++) cols.push(info.start + i)

  return (
    <div className="rounded border border-stone-800 bg-stone-950 p-1.5">
      <div className="mb-1 flex items-baseline justify-between gap-2 px-1">
        <span className="font-mono text-[10px] text-stone-400">{label}</span>
        <span className="text-[9px] text-stone-600">
          {info.count} × {info.width}×{info.height}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {cols.map((col) => {
          const url = api.sheetFrameUrl(info.sheet_path, info.row, col) + `&_=${bust}`
          return (
            <button
              key={col}
              type="button"
              onClick={() => setEditingCol(col)}
              title={`row ${info.row} · col ${col} — click to edit`}
              className="group relative h-14 w-14 overflow-hidden rounded border border-stone-800 bg-stone-950 hover:border-emerald-600"
            >
              <img
                src={url}
                alt={`frame ${col}`}
                className="h-full w-full object-contain"
                style={{ imageRendering: "pixelated" }}
              />
              <span className="absolute bottom-0 right-0 rounded-tl bg-stone-900/80 px-1 text-[9px] text-stone-400 group-hover:text-emerald-300">
                {col}
              </span>
              <Pencil className="absolute right-0.5 top-0.5 h-3 w-3 text-emerald-400 opacity-0 group-hover:opacity-100" />
            </button>
          )
        })}
      </div>
      {editingCol !== null && (
        <PixelEditor
          imageUrl={api.sheetFrameUrl(info.sheet_path, info.row, editingCol)}
          repoPath={info.sheet_path}
          frameTarget={{
            sheet_path: info.sheet_path,
            row: info.row,
            col: editingCol,
          }}
          onClose={() => setEditingCol(null)}
          onSaved={() => { setBust((b) => b + 1); onPixelSaved?.() }}
        />
      )}
    </div>
  )
}

interface ThumbProps {
  url: string
  path: string
  onPixelSaved?: () => void
}

function StageImageThumb({ url, path, onPixelSaved }: ThumbProps) {
  const [broken, setBroken] = useState(false)
  const [editing, setEditing] = useState(false)
  // Per-direction row crops are returned as wide strips (N frames × 92px tall).
  // Render them in a wide container so frames stay legible; whole-sheet links
  // and rotation PNGs keep the square 80×80 thumb.
  const isRowCrop = url.includes("/api/asset/sheet-row")
  // Display label: for "sheet.png#walk_east" surface "walk_east"; otherwise
  // use the filename.
  const fragment = path.includes("#") ? path.split("#").pop() : null
  const label = fragment ?? path.split("/").pop() ?? path

  // Pixel-edit only files we can address by repo path. Row crops are
  // server-cropped on the fly; editing them would need a "patch back into
  // sheet at offset" backend op (out of scope for v1 editor).
  const editableRepoPath = (() => {
    if (isRowCrop) return null
    const match = url.match(/[?&]p=([^&]+)/)
    return match ? decodeURIComponent(match[1]) : null
  })()

  const containerCls = isRowCrop
    ? "group relative overflow-hidden rounded border border-stone-800 bg-stone-950 hover:border-stone-600"
    : "group relative block w-20 overflow-hidden rounded border border-stone-800 bg-stone-950 hover:border-stone-600"
  const innerCls = isRowCrop
    ? "flex h-12 items-center justify-start bg-stone-950"
    : "flex h-20 w-20 items-center justify-center bg-stone-950"

  return (
    <div className={containerCls} title={path}>
      <a href={url} target="_blank" rel="noreferrer" className="block">
        <div className={innerCls}>
          {broken ? (
            <ImageOff className="h-6 w-6 text-stone-700" />
          ) : (
            <img
              src={url}
              alt={label}
              className={
                isRowCrop
                  ? "h-full w-auto object-contain"
                  : "max-h-full max-w-full object-contain"
              }
              onError={() => setBroken(true)}
              style={{ imageRendering: "pixelated" }}
            />
          )}
        </div>
        <div className="truncate px-1 py-0.5 text-[9px] text-stone-500 group-hover:text-stone-300">
          {label}
        </div>
      </a>
      {editableRepoPath && !broken && (
        <button
          type="button"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setEditing(true) }}
          title="Edit pixels"
          className="absolute right-0.5 top-0.5 rounded bg-stone-900/80 p-1 text-stone-300 opacity-0 transition-opacity hover:bg-stone-700 hover:text-stone-100 group-hover:opacity-100"
        >
          <Pencil className="h-3 w-3" />
        </button>
      )}
      {editing && editableRepoPath && (
        <PixelEditor
          imageUrl={url}
          repoPath={editableRepoPath}
          onClose={() => setEditing(false)}
          onSaved={onPixelSaved}
        />
      )}
    </div>
  )
}
