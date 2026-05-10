import type { AssetSummary } from "../types"
import { AssetCard } from "./AssetCard"

interface Props {
  assets: AssetSummary[]
}

export function AssetGrid({ assets }: Props) {
  if (assets.length === 0) {
    return <p className="text-stone-500">No assets match these filters.</p>
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {assets.map((a) => (
        <AssetCard key={`${a.asset_type}:${a.name}`} asset={a} />
      ))}
    </div>
  )
}
