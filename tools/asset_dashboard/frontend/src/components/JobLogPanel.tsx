import { useEffect, useState } from "react"
import { Loader2, X } from "lucide-react"
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
            <button onClick={() => setOpen(false)}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <ul className="max-h-48 overflow-y-auto">
            {jobs.length === 0 && (
              <li className="px-3 py-2 text-xs text-stone-500">No jobs yet.</li>
            )}
            {jobs.map((j) => (
              <li
                key={j.id}
                className={`cursor-pointer border-b border-stone-800 px-3 py-2 text-xs hover:bg-stone-800
                  ${selected === j.id ? "bg-stone-800" : ""}`}
                onClick={() => setSelected(j.id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono">{j.asset_name ?? j.id}</span>
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
                </div>
                <div className="text-[10px] text-stone-500">
                  {j.stage ?? "—"}
                </div>
              </li>
            ))}
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
