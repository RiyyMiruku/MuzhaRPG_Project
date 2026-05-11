import { useEffect, useMemo, useState } from "react"
import { Plus } from "lucide-react"
import type { AssetSummary } from "./types"
import { api } from "./api"
import { FilterBar, applyFilter, makeInitialFilter } from "./components/FilterBar"
import { AssetGrid } from "./components/AssetGrid"
import { AssetDetail } from "./components/AssetDetail"
import { JobLogPanel } from "./components/JobLogPanel"
import { CreateAssetModal } from "./components/CreateAssetModal"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(makeInitialFilter())
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

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
  const selectedAsset = useMemo(
    () => assets.find((a) => `${a.asset_type}:${a.name}` === selectedKey) ?? null,
    [assets, selectedKey]
  )

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <div className="flex items-center gap-3">
          {!selectedAsset && (
            <span className="text-sm text-stone-400">
              {visible.length} of {assets.length} assets
            </span>
          )}
          {!selectedAsset && (
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="flex items-center gap-1 rounded bg-emerald-700 px-3 py-1.5 text-sm text-emerald-50 hover:bg-emerald-600"
            >
              <Plus className="h-4 w-4" />
              New asset
            </button>
          )}
        </div>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      {selectedAsset ? (
        <AssetDetail
          asset={selectedAsset}
          onBack={() => setSelectedKey(null)}
          onDeleted={() => setSelectedKey(null)}
        />
      ) : (
        <>
          <FilterBar filter={filter} onChange={setFilter} assets={assets} />
          {loading ? (
            <p className="text-stone-400">Loading…</p>
          ) : (
            <AssetGrid
              assets={visible}
              onSelect={(a) => setSelectedKey(`${a.asset_type}:${a.name}`)}
            />
          )}
        </>
      )}
      <JobLogPanel />
      <CreateAssetModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          // Manifest poller (2s) will pick up the new asset entry.
          // Nothing else to do — JobLogPanel will show the running job.
        }}
      />
    </div>
  )
}
