import { useState } from "react"
import { ArrowLeft, Trash2, RefreshCw } from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"
import { AssetPreview } from "./AssetPreview"
import { StageSection } from "./StageSection"

interface Props {
  asset: AssetSummary
  onBack: () => void
  onDeleted?: () => void
}

export function AssetDetail({ asset, onBack, onDeleted }: Props) {
  const completed = new Set(asset.completed_stages)
  // Bumped whenever a pixel edit saves — propagates to AssetPreview (which
  // re-fetches the sheet PNG/atlas) and to each StageSection (which re-fetches
  // its stage detail so new frame thumbs are cache-busted).
  const [refreshKey, setRefreshKey] = useState(0)
  const bumpRefresh = () => setRefreshKey((k) => k + 1)
  const [syncing, setSyncing] = useState(false)

  const onSyncFromPixellab = async () => {
    if (!window.confirm(
      `Sync "${asset.name}" from Pixellab?\n\n` +
      `Pulls latest rotations + animations from Pixellab → overwrites local. ` +
      `0 Pixellab credits (only downloads existing frames).\n\n` +
      `Use this when you've edited the character on pixellab.ai's website ` +
      `(mirror direction / draw / template regen) and want to reconcile back.`
    )) return
    setSyncing(true)
    try {
      const result = await api.syncFromPixellab(asset.name, "all")
      const rotCount = Object.keys(result.rotations || {}).length
      const baked = result.animations?.baked || {}
      const animSummary = Object.entries(baked)
        .map(([action, dirs]) => `${action}=${(dirs as string[]).length}`).join(", ")
      window.alert(
        `Synced "${asset.name}" from Pixellab:\n\n` +
        `  rotations: ${rotCount} directions\n` +
        `  animations: ${animSummary || "(none)"}`
      )
      bumpRefresh()
    } catch (e) {
      window.alert(`Sync failed: ${(e as Error).message}`)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 rounded bg-stone-800 px-3 py-1.5 text-sm hover:bg-stone-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to grid
        </button>
        <div className="flex gap-2">
          {asset.asset_type === "character" && (
            <button
              type="button"
              onClick={onSyncFromPixellab}
              disabled={syncing}
              className="flex items-center gap-1 rounded bg-sky-900/40 px-3 py-1.5 text-sm text-sky-200 hover:bg-sky-900/60 disabled:opacity-50"
              title="Pull latest rotations + animations from pixellab.ai (0 credits)"
            >
              <RefreshCw className={"h-4 w-4 " + (syncing ? "animate-spin" : "")} />
              {syncing ? "Syncing…" : "Sync from Pixellab"}
            </button>
          )}
          <button
            type="button"
            onClick={async () => {
              if (!window.confirm(
                `Delete "${asset.name}"?\n\n` +
                `This removes the manifest entry AND deletes local files:\n` +
                `  • art_source/<bucket>/${asset.name}/ (rotations, spritesheet, etc.)\n` +
                `  • game/assets/textures/... imported copies (PNG/JSON/tscn + .import sidecars)\n\n` +
                `This cannot be undone. Continue?`
              )) return
              try {
                const result = await api.deleteAsset(asset.asset_type, asset.name)
                if (result.file_errors && result.file_errors.length > 0) {
                  window.alert(
                    `Deleted "${asset.name}" with some file errors:\n\n` +
                    result.file_errors.join("\n")
                  )
                }
                onDeleted?.()
                onBack()
              } catch (e) {
                window.alert(`Delete failed: ${(e as Error).message}`)
              }
            }}
            className="flex items-center gap-1 rounded bg-red-900/40 px-3 py-1.5 text-sm text-red-200 hover:bg-red-900/60"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Big zoomable preview — first thing on the page. Animated for characters
          with a spritesheet, static for everything else. */}
      <section className="mb-6">
        <AssetPreview asset={asset} refreshKey={refreshKey} />
      </section>

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
              refreshKey={refreshKey}
              onPixelSaved={bumpRefresh}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
