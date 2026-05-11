import type { AssetSummary } from "../types"
import { AssetCard } from "./AssetCard"

interface Props {
  assets: AssetSummary[]
  onSelect: (asset: AssetSummary) => void
}

export function AssetGrid({ assets, onSelect }: Props) {
  if (assets.length === 0) {
    return <p className="text-stone-500">No assets match these filters.</p>
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {assets.map((a) => (
        <AssetCard key={`${a.asset_type}:${a.name}`} asset={a} onSelect={onSelect} />
      ))}
    </div>
  )
}
