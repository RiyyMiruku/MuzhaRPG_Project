import { useState } from "react"
import { ImageOff } from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"
import { StageList } from "./StageList"
import { HoverSpritePreview } from "./HoverSpritePreview"

interface Props {
  asset: AssetSummary
  onSelect: (asset: AssetSummary) => void
}

// Stage names that mean "the spritesheet has at least one usable animation row".
// Cover both v2 (animate_*) and legacy (add_*_animation) so cards from either
// pipeline animate on hover.
const ANIMATION_STAGE_DONE = (asset: AssetSummary): boolean =>
  asset.asset_type === "character" &&
  (asset.completed_stages.includes("animate_idle") ||
    asset.completed_stages.includes("animate_walk") ||
    asset.completed_stages.includes("add_idle_animation") ||
    asset.completed_stages.includes("add_walk_animation"))

export function AssetCard({ asset, onSelect }: Props) {
  const [thumbBroken, setThumbBroken] = useState(false)
  const [hovered, setHovered] = useState(false)
  const thumbUrl = api.thumbnailUrl(asset.asset_type, asset.name)
  const canAnimate = ANIMATION_STAGE_DONE(asset)

  return (
    <button
      type="button"
      onClick={() => onSelect(asset)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="block w-full rounded-lg border border-stone-800 bg-stone-900 p-4 text-left transition hover:border-stone-600 hover:bg-stone-800"
    >
      <div className="relative mb-3 flex h-32 items-center justify-center overflow-hidden rounded bg-stone-950">
        {thumbBroken ? (
          <ImageOff className="h-10 w-10 text-stone-700" />
        ) : (
          <>
            {/* Static thumbnail underneath. */}
            <img
              src={thumbUrl}
              alt={asset.name}
              className="max-h-full max-w-full object-contain"
              onError={() => setThumbBroken(true)}
              style={{
                imageRendering: "pixelated",
                transform: asset.extra.flip_h ? "scaleX(-1)" : undefined,
              }}
            />
            {/* Animated overlay — keep mounted across hover toggles so the
                first lazy-load is shared with later hovers. Transparent
                background lets the static thumbnail show through during
                fetch (otherwise hover flashes black). */}
            {canAnimate && (
              <div
                className={
                  "pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity " +
                  (hovered ? "opacity-100" : "opacity-0")
                }
              >
                <HoverSpritePreview
                  characterName={asset.name}
                  play={hovered}
                />
              </div>
            )}
          </>
        )}
      </div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="truncate font-mono text-sm font-semibold">{asset.name}</h3>
        <span className="text-xs text-stone-500">{asset.progress}</span>
      </div>
      <div className="mb-3 flex flex-wrap gap-1">
        {asset.tags.map((t) => (
          <span
            key={t}
            className="rounded bg-stone-800 px-2 py-0.5 text-[10px] text-stone-400"
          >
            {t}
          </span>
        ))}
      </div>
      <StageList asset={asset} />
    </button>
  )
}
