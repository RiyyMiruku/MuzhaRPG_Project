import type { AssetSummary, AssetType } from "../types"

export interface FilterState {
  search: string
  assetType: AssetType | "all"
  chapter: string | "all"
  zone: string | "all"
  status: "all" | "in_progress" | "complete"
}

export function makeInitialFilter(): FilterState {
  return { search: "", assetType: "all", chapter: "all", zone: "all", status: "all" }
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

  // Cascade: zone options come from assets that pass the current chapter filter
  // (other filters intentionally don't cascade — search is fuzzy, type/status
  // shouldn't hide zone choices). "*" sentinel never appears as a selectable
  // option; it's a property of *which assets count* under a chosen zone.
  const zoneScopedAssets =
    filter.chapter === "all"
      ? assets
      : assets.filter((a) => a.chapter === filter.chapter)
  const zoneSlugs = Array.from(
    new Set(zoneScopedAssets.flatMap((a) => a.zones).filter((z) => z !== "*"))
  ).sort()

  // If a previously-selected zone is no longer in the scoped list (e.g. user
  // switched chapters), reset it to "all" via the next change handler call.
  const zoneStillValid = filter.zone === "all" || zoneSlugs.includes(filter.zone)

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
        onChange={(e) => {
          const newChapter = e.target.value
          // Reset zone when changing chapter so we don't leave a stale slug
          // selected that has no entries in the new scope.
          onChange({ ...filter, chapter: newChapter, zone: "all" })
        }}
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
        value={zoneStillValid ? filter.zone : "all"}
        onChange={(e) => onChange({ ...filter, zone: e.target.value })}
        disabled={zoneSlugs.length === 0}
      >
        <option value="all">
          {zoneSlugs.length === 0 ? "(no zones)" : "All zones"}
        </option>
        {zoneSlugs.map((z) => (
          <option key={z} value={z}>
            {z}
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
    if (filter.zone !== "all") {
      // Assets with "*" sentinel (cross-zone / shared) count under any zone.
      if (!a.zones.includes(filter.zone) && !a.zones.includes("*")) return false
    }
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
