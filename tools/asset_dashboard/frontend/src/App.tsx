import { useEffect, useState } from "react"
import type { AssetSummary } from "./types"
import { api } from "./api"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

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

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <span className="text-sm text-stone-400">{assets.length} assets</span>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-stone-400">Loading…</p>
      ) : (
        <pre className="rounded bg-stone-900 p-4 text-xs text-stone-300">
          {JSON.stringify(assets.slice(0, 3), null, 2)}
        </pre>
      )}
    </div>
  )
}
