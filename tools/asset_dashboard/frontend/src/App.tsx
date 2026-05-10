import { useEffect, useState } from "react"
import type { AssetSummary } from "./types"
import { api } from "./api"
import { FilterBar, applyFilter, makeInitialFilter } from "./components/FilterBar"
import { AssetGrid } from "./components/AssetGrid"
import { JobLogPanel } from "./components/JobLogPanel"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(makeInitialFilter())

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const data = await api.manifest()
        if (!stopped) {
          setAssets(data.assets)
          setError(null)
        }
      } catch (e) {
        if (!stopped) setError((e as Error).message)
      } finally {
        if (!stopped) setLoading(false)
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  const visible = applyFilter(assets, filter)

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <span className="text-sm text-stone-400">
          {visible.length} of {assets.length} assets
        </span>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <FilterBar filter={filter} onChange={setFilter} assets={assets} />
      {loading ? <p className="text-stone-400">Loading…</p> : <AssetGrid assets={visible} />}
      <JobLogPanel />
    </div>
  )
}
