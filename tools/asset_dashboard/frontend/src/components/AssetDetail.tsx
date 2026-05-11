import { ArrowLeft } from "lucide-react"
import type { AssetSummary } from "../types"
import { SpritePreview } from "./SpritePreview"
import { StageSection } from "./StageSection"

interface Props {
  asset: AssetSummary
  onBack: () => void
}

export function AssetDetail({ asset, onBack }: Props) {
  const completed = new Set(asset.completed_stages)
  const hasSpritesheet =
    asset.asset_type === "character" && completed.has("compile_spritesheet")

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-4 flex items-center gap-1 rounded bg-stone-800 px-3 py-1.5 text-sm hover:bg-stone-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to grid
      </button>

      <div className="mb-6 rounded-lg border border-stone-800 bg-stone-900 p-6">
        <div className="mb-2 flex items-baseline justify-between gap-4">
          <h2 className="font-mono text-2xl font-semibold">{asset.name}</h2>
          <span className="text-sm text-stone-500">
            {asset.asset_type} · {asset.progress}
          </span>
        </div>
        <div className="mb-3 flex flex-wrap gap-1">
          {asset.tags.map((t) => (
            <span
              key={t}
              className="rounded bg-stone-800 px-2 py-0.5 text-xs text-stone-400"
            >
              {t}
            </span>
          ))}
        </div>
        {asset.description && (
          <p className="text-sm text-stone-400">{asset.description}</p>
        )}
      </div>

      {hasSpritesheet && (
        <section className="mb-6">
          <h3 className="mb-3 text-sm font-semibold text-stone-300">
            Sprite preview
          </h3>
          <SpritePreview characterName={asset.name} />
        </section>
      )}

      <section className="mb-6">
        <h3 className="mb-3 text-sm font-semibold text-stone-300">
          Stages &amp; prompts
        </h3>
        <div className="space-y-3">
          {asset.all_stages.map((stage) => (
            <StageSection
              key={stage}
              asset={asset}
              stage={stage}
              realized={completed.has(stage)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
