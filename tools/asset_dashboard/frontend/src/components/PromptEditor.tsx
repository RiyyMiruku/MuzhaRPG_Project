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

/** Prompt-driven stage editor (description / atlas / object prompts).
 *  Template-driven animation stages (animate_*, add_*_animation) bypass this
 *  component and render TemplateAnimRemake instead — they have no prompt
 *  semantics and no per-direction needs that PromptEditor handles. */
export function PromptEditor({ asset, stage, initialPrompt, realized }: Props) {
  const [text, setText] = useState(initialPrompt)
  const [unlocked, setUnlocked] = useState(!realized)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      if (realized && unlocked) {
        await api.remake(asset.asset_type, asset.name, stage, text)
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
            disabled={submitting || (text === initialPrompt && !realized)}
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
