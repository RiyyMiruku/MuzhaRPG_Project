import type { AssetSummary, AssetType } from "../types"

export interface FilterState {
  search: string
  assetType: AssetType | "all"
  chapter: string | "all"
  status: "all" | "in_progress" | "complete"
}

export function makeInitialFilter(): FilterState {
  return { search: "", assetType: "all", chapter: "all", status: "all" }
}

interface Props {
  filter: FilterState
  onChange: (f: FilterState) => void
  assets: AssetSummary[]
}

export function FilterBar({ filter, onChange, assets }: Props) {
  const chapters = Array.from(
    new Set(assets.map((a) => a.chapter).filter((c): c is string => c !== null))
  ).sort()

  return (
    <div className="mb-6 flex flex-wrap gap-3">
      <input
        type="text"
        placeholder="Search by name or description…"
        className="rounded bg-stone-800 px-3 py-2 text-sm placeholder:text-stone-500 focus:outline-none focus:ring-1 focus:ring-stone-500"
        value={filter.search}
        onChange={(e) => onChange({ ...filter, search: e.target.value })}
      />
      <select
        className="rounded bg-stone-800 px-3 py-2 text-sm"
        value={filter.assetType}
        onChange={(e) =>
          onChange({ ...filter, assetType: e.target.value as FilterState["assetType"] })
        }
      >
        <option value="all">All types</option>
        <option value="character">Characters</option>
        <option value="object">Props / Buildings</option>
        <option value="tileset">Tilesets</option>
      </select>
      <select
        className="rounded bg-stone-800 px-3 py-2 text-sm"
        value={filter.chapter}
        onChange={(e) => onChange({ ...filter, chapter: e.target.value })}
      >
        <option value="all">All chapters</option>
        {chapters.map((c) => (
          <option key={c} value={c}>
            Chapter {c}
          </option>
        ))}
      </select>
      <select
        className="rounded bg-stone-800 px-3 py-2 text-sm"
        value={filter.status}
        onChange={(e) =>
          onChange({ ...filter, status: e.target.value as FilterState["status"] })
        }
      >
        <option value="all">Any status</option>
        <option value="in_progress">In progress</option>
        <option value="complete">Complete</option>
      </select>
    </div>
  )
}

export function applyFilter(assets: AssetSummary[], filter: FilterState): AssetSummary[] {
  return assets.filter((a) => {
    if (filter.assetType !== "all" && a.asset_type !== filter.assetType) return false
    if (filter.chapter !== "all" && a.chapter !== filter.chapter) return false
    if (filter.status === "in_progress" && a.completed_stages.length === a.all_stages.length)
      return false
    if (filter.status === "complete" && a.completed_stages.length !== a.all_stages.length)
      return false
    if (filter.search.trim()) {
      const needle = filter.search.toLowerCase()
      const hay = (a.name + " " + (a.description ?? "")).toLowerCase()
      if (!hay.includes(needle)) return false
    }
    return true
  })
}
