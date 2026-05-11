import { useEffect, useState } from "react"
import { Check, Circle, ImageOff } from "lucide-react"
import type { AssetSummary, StageDetail } from "../types"
import { api } from "../api"
import { PromptEditor } from "./PromptEditor"

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

      <PromptEditor
        asset={asset}
        stage={stage}
        initialPrompt={initialPrompt}
        realized={realized}
      />
    </section>
  )
}

interface StripProps {
  images: { path: string; url: string }[]
}

function StageImageStrip({ images }: StripProps) {
  return (
    <div className="mb-3 flex flex-wrap gap-2 rounded bg-stone-950 p-2">
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
  const filename = path.split("/").pop() ?? path

  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="group block w-20 overflow-hidden rounded border border-stone-800 bg-stone-950 hover:border-stone-600"
      title={path}
    >
      <div className="flex h-20 w-20 items-center justify-center bg-stone-950">
        {broken ? (
          <ImageOff className="h-6 w-6 text-stone-700" />
        ) : (
          <img
            src={url}
            alt={filename}
            className="max-h-full max-w-full object-contain"
            onError={() => setBroken(true)}
            style={{ imageRendering: "pixelated" }}
          />
        )}
      </div>
      <div className="truncate px-1 py-0.5 text-[9px] text-stone-500 group-hover:text-stone-300">
        {filename}
      </div>
    </a>
  )
}
