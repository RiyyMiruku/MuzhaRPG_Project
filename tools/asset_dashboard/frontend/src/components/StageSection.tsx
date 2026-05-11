import { useEffect, useState } from "react"
import { Check, Circle, ImageOff, Play, RotateCcw } from "lucide-react"
import type { AssetSummary, StageDetail } from "../types"
import { api } from "../api"
import { PromptEditor } from "./PromptEditor"

/** Stages that send a prompt to Pixellab. Other stages are pure local processing
 *  (chroma_key / iso_project / verify_in_godot / compile_spritesheet / import_to_godot)
 *  and have no editable prompt — only a plain "re-run this stage" button. */
const PROMPT_STAGES = new Set<string>([
  "generate_8dir_base",
  "generate_4dir_base",
  "generate_object",
  "generate_atlas",
  "add_idle_animation",
  "add_walk_animation",
])

interface Props {
  asset: AssetSummary
  stage: string
  realized: boolean
  /** Bumps when a remake/submit happens elsewhere, forces refetch. */
  refreshKey?: number
}

export function StageSection({ asset, stage, realized, refreshKey }: Props) {
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
        <StageImageStrip images={detail.images} />
      )}

      {hasPrompt ? (
        <PromptEditor
          asset={asset}
          stage={stage}
          initialPrompt={initialPrompt}
          realized={realized}
        />
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

interface StripProps {
  images: { path: string; url: string }[]
}

function StageImageStrip({ images }: StripProps) {
  // If any image is a row crop, stack vertically (wide strips don't tile well
  // side-by-side). Otherwise keep the original wrap-grid for square thumbs.
  const hasRowCrop = images.some((i) => i.url.includes("/api/asset/sheet-row"))
  const layoutCls = hasRowCrop
    ? "mb-3 flex flex-col gap-1.5 rounded bg-stone-950 p-2"
    : "mb-3 flex flex-wrap gap-2 rounded bg-stone-950 p-2"
  return (
    <div className={layoutCls}>
      {images.map((img) => (
        <StageImageThumb key={img.path} url={img.url} path={img.path} />
      ))}
    </div>
  )
}

interface ThumbProps {
  url: string
  path: string
}

function StageImageThumb({ url, path }: ThumbProps) {
  const [broken, setBroken] = useState(false)
  // Per-direction row crops are returned as wide strips (N frames × 92px tall).
  // Render them in a wide container so frames stay legible; whole-sheet links
  // and rotation PNGs keep the square 80×80 thumb.
  const isRowCrop = url.includes("/api/asset/sheet-row")
  // Display label: for "sheet.png#walk_east" surface "walk_east"; otherwise
  // use the filename.
  const fragment = path.includes("#") ? path.split("#").pop() : null
  const label = fragment ?? path.split("/").pop() ?? path

  const containerCls = isRowCrop
    ? "group block overflow-hidden rounded border border-stone-800 bg-stone-950 hover:border-stone-600"
    : "group block w-20 overflow-hidden rounded border border-stone-800 bg-stone-950 hover:border-stone-600"
  const innerCls = isRowCrop
    ? "flex h-12 items-center justify-start bg-stone-950"
    : "flex h-20 w-20 items-center justify-center bg-stone-950"

  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className={containerCls}
      title={path}
    >
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
  )
}
