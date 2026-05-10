import { Check, Circle } from "lucide-react"
import type { AssetSummary } from "../types"

interface Props {
  asset: AssetSummary
}

export function StageList({ asset }: Props) {
  const completed = new Set(asset.completed_stages)
  return (
    <ol className="space-y-1 text-sm">
      {asset.all_stages.map((stage) => {
        const done = completed.has(stage)
        return (
          <li key={stage} className="flex items-center gap-2">
            {done ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <Circle className="h-4 w-4 text-stone-600" />
            )}
            <span className={done ? "text-stone-200" : "text-stone-500"}>
              {stage}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
