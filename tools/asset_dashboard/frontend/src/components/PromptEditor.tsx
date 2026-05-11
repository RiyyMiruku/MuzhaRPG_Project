import { useState } from "react"
import { Lock, Unlock, Send, RotateCcw } from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"

interface Props {
  asset: AssetSummary
  stage: string
  initialPrompt: string
  realized: boolean
}

// Direction lists per animation stage, in display order. Stages not listed
// here have no per-direction selector. Values must match Pixellab's wire form.
const STAGE_DIRECTIONS: Record<string, string[]> = {
  add_idle_animation: ["south", "east", "north", "west"],
  add_walk_animation: [
    "south", "east", "north", "west",
    "south-east", "north-east", "north-west", "south-west",
  ],
}

export function PromptEditor({ asset, stage, initialPrompt, realized }: Props) {
  const [text, setText] = useState(initialPrompt)
  const [unlocked, setUnlocked] = useState(!realized)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const availableDirs = STAGE_DIRECTIONS[stage] ?? []
  const [selectedDirs, setSelectedDirs] = useState<Set<string>>(
    () => new Set(availableDirs)
  )

  const toggleDir = (d: string) => {
    setSelectedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(d)) next.delete(d)
      else next.add(d)
      return next
    })
  }
  const allSelected =
    availableDirs.length > 0 &&
    availableDirs.every((d) => selectedDirs.has(d))
  const partial = !allSelected && selectedDirs.size > 0

  const onSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      if (realized && unlocked) {
        // Pass directions only when user has narrowed the set; an empty/full
        // selection means "regen all" (server treats undefined the same).
        const dirsToPass =
          availableDirs.length > 0 && partial
            ? availableDirs.filter((d) => selectedDirs.has(d))
            : undefined
        await api.remake(asset.asset_type, asset.name, stage, text, dirsToPass)
      } else {
        await api.patchPrompt(asset.asset_type, asset.name, stage, text)
      }
      setUnlocked(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const onRemake = () => {
    if (window.confirm(`Remake stage "${stage}"? 此 stage 之後的下游 stage 不會自動失效,需要分別 remake。`)) {
      setUnlocked(true)
    }
  }

  const editable = unlocked && !submitting

  return (
    <div className="mt-2 rounded border border-stone-800 bg-stone-950 p-2">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-mono text-stone-400">{stage}</span>
        {realized && !unlocked && (
          <span className="flex items-center gap-1 text-stone-600">
            <Lock className="h-3 w-3" /> realized
          </span>
        )}
        {unlocked && (
          <span className="flex items-center gap-1 text-amber-400">
            <Unlock className="h-3 w-3" /> editable
          </span>
        )}
      </div>
      <textarea
        className={`w-full rounded px-2 py-1 text-xs font-mono leading-relaxed
          ${editable ? "bg-stone-800 text-stone-100" : "bg-stone-900 text-stone-500"}`}
        rows={2}
        value={text}
        readOnly={!editable}
        onChange={(e) => setText(e.target.value)}
      />
      {availableDirs.length > 0 && unlocked && (
        <div className="mt-2 rounded border border-stone-800 bg-stone-900 px-2 py-1.5">
          <div className="mb-1 flex items-center justify-between text-[10px]">
            <span className="text-stone-400">
              Regen directions
              {partial && (
                <span className="ml-1 text-amber-400">(partial)</span>
              )}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setSelectedDirs(new Set(availableDirs))}
                className="text-stone-500 hover:text-stone-300"
              >
                all
              </button>
              <button
                type="button"
                onClick={() => setSelectedDirs(new Set())}
                className="text-stone-500 hover:text-stone-300"
              >
                none
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {availableDirs.map((d) => {
              const active = selectedDirs.has(d)
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDir(d)}
                  className={
                    "rounded border px-1.5 py-0.5 text-[10px] font-mono " +
                    (active
                      ? "border-emerald-700 bg-emerald-900/40 text-emerald-100"
                      : "border-stone-700 bg-stone-950 text-stone-500 hover:border-stone-600")
                  }
                >
                  {d}
                </button>
              )
            })}
          </div>
          <p className="mt-1 text-[10px] text-stone-500">
            勾起來的方向才會重生 Pixellab credit;全選 = 等同舊行為,partial
            模式 spritesheet 只 patch 對應 row,不會全重組。
          </p>
        </div>
      )}
      <div className="mt-1 flex items-center gap-2">
        {realized && !unlocked && (
          <button
            type="button"
            onClick={onRemake}
            className="flex items-center gap-1 rounded bg-stone-800 px-2 py-1 text-xs hover:bg-stone-700"
          >
            <RotateCcw className="h-3 w-3" />
            Remake
          </button>
        )}
        {editable && (
          <button
            type="button"
            disabled={
              submitting ||
              (text === initialPrompt &&
                (!realized ||
                  availableDirs.length === 0 ||
                  allSelected))
            }
            onClick={onSubmit}
            className="flex items-center gap-1 rounded bg-emerald-700 px-2 py-1 text-xs text-emerald-50 disabled:bg-stone-700 disabled:text-stone-500"
          >
            <Send className="h-3 w-3" />
            {submitting ? "Submitting…" : realized ? "Remake & Submit" : "Submit"}
          </button>
        )}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </div>
  )
}
