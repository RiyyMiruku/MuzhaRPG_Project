import { useEffect, useState } from "react"
import { Loader2, Trash2, X } from "lucide-react"
import type { JobInfo } from "../types"
import { api } from "../api"

export function JobLogPanel() {
  const [jobs, setJobs] = useState<JobInfo[]>([])
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [tail, setTail] = useState("")

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const r = await api.jobs()
        if (!stopped) setJobs(r.jobs)
      } catch {
        /* ignore transient errors */
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  useEffect(() => {
    if (!selected) return
    let stopped = false
    const tick = async () => {
      try {
        const j = await api.jobDetail(selected)
        if (!stopped) setTail(j.tail ?? "")
      } catch {
        /* ignore */
      }
    }
    tick()
    const id = setInterval(tick, 1500)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [selected])

  const running = jobs.filter((j) => j.status === "running").length
  const finishedCount = jobs.filter(
    (j) => j.status === "completed" || j.status === "failed"
  ).length

  const onClearFinished = async () => {
    if (finishedCount === 0) return
    if (!window.confirm(`Remove ${finishedCount} finished job(s) from this panel?`)) return
    try {
      await api.clearFinishedJobs()
      if (selected && !jobs.find((j) => j.id === selected && j.status === "running")) {
        setSelected(null)
        setTail("")
      }
      // The 2s poll will refresh the list; no manual refetch needed.
    } catch (e) {
      window.alert(`Clear failed: ${(e as Error).message}`)
    }
  }

  const onRemoveOne = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.deleteJob(jobId)
      if (selected === jobId) {
        setSelected(null)
        setTail("")
      }
    } catch (err) {
      window.alert(`Remove failed: ${(err as Error).message}`)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-4 right-4 flex items-center gap-2 rounded-full bg-stone-800 px-4 py-2 text-sm shadow-lg hover:bg-stone-700"
      >
        {running > 0 && <Loader2 className="h-4 w-4 animate-spin text-amber-400" />}
        Jobs ({jobs.length})
      </button>
      {open && (
        <div className="fixed bottom-16 right-4 max-h-[70vh] w-96 overflow-hidden rounded-lg border border-stone-700 bg-stone-900 shadow-xl">
          <div className="flex items-center justify-between border-b border-stone-800 px-3 py-2">
            <span className="text-sm font-semibold">Jobs</span>
            <div className="flex items-center gap-2">
              {finishedCount > 0 && (
                <button
                  type="button"
                  onClick={onClearFinished}
                  className="flex items-center gap-1 rounded bg-stone-800 px-2 py-0.5 text-[10px] text-stone-300 hover:bg-stone-700"
                  title={`Clear ${finishedCount} finished job(s)`}
                >
                  <Trash2 className="h-3 w-3" />
                  Clear finished ({finishedCount})
                </button>
              )}
              <button onClick={() => setOpen(false)}>
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
          <ul className="max-h-48 overflow-y-auto">
            {jobs.length === 0 && (
              <li className="px-3 py-2 text-xs text-stone-500">No jobs yet.</li>
            )}
            {jobs.map((j) => {
              const removable = j.status === "completed" || j.status === "failed"
              return (
                <li
                  key={j.id}
                  className={`group cursor-pointer border-b border-stone-800 px-3 py-2 text-xs hover:bg-stone-800
                    ${selected === j.id ? "bg-stone-800" : ""}`}
                  onClick={() => setSelected(j.id)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono">{j.asset_name ?? j.id}</span>
                    <div className="flex items-center gap-2">
                      <span
                        className={
                          j.status === "running"
                            ? "text-amber-400"
                            : j.status === "completed"
                            ? "text-emerald-400"
                            : j.status === "failed"
                            ? "text-red-400"
                            : "text-stone-500"
                        }
                      >
                        {j.status}
                      </span>
                      {removable && (
                        <button
                          type="button"
                          onClick={(e) => onRemoveOne(j.id, e)}
                          className="rounded p-0.5 text-stone-500 opacity-0 hover:bg-stone-700 hover:text-stone-200 group-hover:opacity-100"
                          title="Remove from panel"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="text-[10px] text-stone-500">
                    {j.stage ?? "—"}
                  </div>
                </li>
              )
            })}
          </ul>
          {selected && (
            <pre className="max-h-72 overflow-auto bg-stone-950 p-3 text-[10px] leading-snug text-stone-300">
              {tail || "(no output yet)"}
            </pre>
          )}
        </div>
      )}
    </>
  )
}
