import { useState } from "react"
import { X, Plus } from "lucide-react"
import type {
  AssetType,
  CharacterKind,
  CharacterView,
  CreateAssetBody,
  ObjectKind,
  Proportions,
} from "../types"
import { api } from "../api"

type AssetKindOption =
  | { type: "character"; kind: CharacterKind; label: string }
  | { type: "tileset"; kind: null; label: string }
  | { type: "object"; kind: ObjectKind; label: string }

const KIND_OPTIONS: AssetKindOption[] = [
  { type: "character", kind: "moving", label: "Moving NPC / Player (8-dir walk + idle)" },
  { type: "character", kind: "static", label: "Static NPC (idle only)" },
  { type: "object", kind: "iso_prop", label: "Iso prop (lantern, cart, decoration — ≤64px)" },
  { type: "object", kind: "iso_building", label: "Iso building (pixflux + isometric — shophouse, temple)" },
  { type: "object", kind: "building", label: "Building (top-down / facade — no iso)" },
  { type: "tileset", kind: null, label: "Autotile (terrain)" },
]

const VIEW_OPTIONS: CharacterView[] = ["high_top_down", "low_top_down", "side"]
const PROPORTIONS_OPTIONS: Proportions[] = [
  "cartoon", "chibi", "stylized", "realistic_male", "realistic_female", "heroic",
]
const COLLISION_OPTIONS = ["bottom_16x16", "bottom_16x8", "full", "none"]

interface Props {
  open: boolean
  onClose: () => void
  /** Called with the new job's asset name so the caller can open JobLogPanel etc. */
  onCreated: (info: { job_id: string; asset_name: string }) => void
}

export function CreateAssetModal({ open, onClose, onCreated }: Props) {
  const [picked, setPicked] = useState<AssetKindOption>(KIND_OPTIONS[0])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // common fields
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [zone, setZone] = useState("")
  const [category, setCategory] = useState("")
  const [chapter, setChapter] = useState("")

  // character-specific
  const [view, setView] = useState<CharacterView>("high_top_down")
  const [proportions, setProportions] = useState<Proportions | "">("")
  const [directions, setDirections] = useState<4 | 8>(8)
  const [idleFrames, setIdleFrames] = useState(4)
  const [walkFrames, setWalkFrames] = useState(8)
  const [noIdle, setNoIdle] = useState(false)

  // object-specific
  const [size, setSize] = useState(32)
  const [width, setWidth] = useState(128)
  const [height, setHeight] = useState(128)
  const [collision, setCollision] = useState("bottom_16x16")
  const [hasCollision, setHasCollision] = useState(true)

  // tileset-specific
  const [lower, setLower] = useState("")
  const [upper, setUpper] = useState("")
  const [transitionSize, setTransitionSize] = useState(0)
  const [transitionDescription, setTransitionDescription] = useState("")

  if (!open) return null

  const resetForm = () => {
    setName(""); setDescription(""); setZone(""); setCategory(""); setChapter("")
    setLower(""); setUpper(""); setTransitionDescription("")
    setError(null)
  }

  const buildBody = (): CreateAssetBody => {
    const base: CreateAssetBody = { asset_type: picked.type as AssetType, name }
    const zoneSlugs = zone
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
    if (zoneSlugs.length > 0) base.zones = zoneSlugs
    if (category) base.category = category
    if (chapter) base.chapter = chapter

    if (picked.type === "character") {
      base.kind = picked.kind
      base.description = description
      base.view = view
      if (proportions) base.proportions = proportions
      base.idle_frame_count = idleFrames
      if (picked.kind === "moving") {
        base.walk_frame_count = walkFrames
      } else {
        base.directions = directions
        if (noIdle) base.no_idle = true
      }
    } else if (picked.type === "object") {
      base.kind = picked.kind
      base.description = description
      base.collision = collision
      base.has_collision = hasCollision
      if (picked.kind === "iso_prop") {
        base.size = size
      } else {
        // building OR iso_building both use width/height/view
        base.width = width
        base.height = height
        base.view = view
      }
    } else {
      // tileset
      base.lower = lower
      base.upper = upper
      base.transition_size = transitionSize
      if (transitionDescription) base.transition_description = transitionDescription
    }
    return base
  }

  const onSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const result = await api.create(buildBody())
      resetForm()
      onCreated({ job_id: result.job_id, asset_name: result.asset_name })
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const isCharacter = picked.type === "character"
  const isObject = picked.type === "object"
  const isTileset = picked.type === "tileset"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-stone-700 bg-stone-900 shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-stone-800 bg-stone-900 px-4 py-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Plus className="h-5 w-5" />
            Create new asset
          </h2>
          <button type="button" onClick={onClose} className="rounded p-1 hover:bg-stone-800">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-4">
          {/* Type picker */}
          <fieldset>
            <legend className="mb-2 text-sm font-semibold text-stone-300">
              Asset type
            </legend>
            <div className="space-y-1.5">
              {KIND_OPTIONS.map((opt, i) => (
                <label
                  key={i}
                  className={`flex cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm
                    ${
                      picked === opt
                        ? "border-emerald-700 bg-emerald-900/20"
                        : "border-stone-800 bg-stone-950 hover:border-stone-600"
                    }`}
                >
                  <input
                    type="radio"
                    name="asset-kind"
                    checked={picked === opt}
                    onChange={() => setPicked(opt)}
                    className="accent-emerald-500"
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* Name */}
          <Field label="Name (lowercase, underscores, e.g. chen_ayi)">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="chen_ayi"
              className="w-full rounded bg-stone-800 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-stone-500"
              autoFocus
            />
          </Field>

          {/* description (for character/object) OR lower/upper (for tileset) */}
          {(isCharacter || isObject) && (
            <Field label="Description (Pixellab prompt for stage 1)">
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="middle-aged taiwanese market vendor, red floral shirt..."
                className="w-full rounded bg-stone-800 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-stone-500"
              />
            </Field>
          )}

          {isTileset && (
            <>
              <Field label="Lower terrain (prompt)">
                <input
                  type="text"
                  value={lower}
                  onChange={(e) => setLower(e.target.value)}
                  placeholder="green grass texture"
                  className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                />
              </Field>
              <Field label="Upper terrain (prompt)">
                <input
                  type="text"
                  value={upper}
                  onChange={(e) => setUpper(e.target.value)}
                  placeholder="dark asphalt road"
                  className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Transition size (Pixellab 限定 enum)">
                  <select
                    value={transitionSize}
                    onChange={(e) => setTransitionSize(parseFloat(e.target.value))}
                    className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                  >
                    <option value={0}>0.0 (無過渡)</option>
                    <option value={0.25}>0.25 (細邊)</option>
                    <option value={0.5}>0.5 (中等)</option>
                    <option value={1}>1.0 (完整 tile)</option>
                  </select>
                </Field>
                <Field label="Transition description (optional)">
                  <input
                    type="text"
                    value={transitionDescription}
                    onChange={(e) => setTransitionDescription(e.target.value)}
                    placeholder="grey concrete curb"
                    className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                  />
                </Field>
              </div>
            </>
          )}

          {/* Character extras */}
          {isCharacter && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="View">
                <select
                  value={view}
                  onChange={(e) => setView(e.target.value as CharacterView)}
                  className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                >
                  {VIEW_OPTIONS.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </Field>
              <Field label="Proportions (optional)">
                <select
                  value={proportions}
                  onChange={(e) =>
                    setProportions(e.target.value === "" ? "" : (e.target.value as Proportions))
                  }
                  className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                >
                  <option value="">(預設:cartoon)</option>
                  {PROPORTIONS_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </Field>
              {picked.kind === "static" && (
                <>
                  <Field label="Directions">
                    <select
                      value={directions}
                      onChange={(e) => setDirections(Number(e.target.value) as 4 | 8)}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    >
                      <option value={8}>8 (full)</option>
                      <option value={4}>4 (cheaper, idle-only forever)</option>
                    </select>
                  </Field>
                  <Field label="Idle frame count">
                    <input
                      type="number"
                      min={1}
                      max={16}
                      value={idleFrames}
                      onChange={(e) => setIdleFrames(parseInt(e.target.value, 10))}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    />
                  </Field>
                  <label className="col-span-2 flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={noIdle}
                      onChange={(e) => setNoIdle(e.target.checked)}
                      className="accent-emerald-500"
                    />
                    <span>Skip idle animation entirely (--no-idle)</span>
                  </label>
                </>
              )}
              {picked.kind === "moving" && (
                <>
                  <Field label="Idle frame count">
                    <input
                      type="number"
                      min={1}
                      max={16}
                      value={idleFrames}
                      onChange={(e) => setIdleFrames(parseInt(e.target.value, 10))}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    />
                  </Field>
                  <Field label="Walk frame count">
                    <input
                      type="number"
                      min={1}
                      max={16}
                      value={walkFrames}
                      onChange={(e) => setWalkFrames(parseInt(e.target.value, 10))}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    />
                  </Field>
                </>
              )}
              <div className="col-span-2 rounded bg-stone-950 px-3 py-2 text-[11px] text-stone-500">
                Idle / Walk 動畫一律用 Pixellab template 模式
                (<span className="font-mono text-stone-400">breathing-idle</span> / <span className="font-mono text-stone-400">walking-N-frames</span>),
                沒有 prompt 可以客製。事後要 partial regen 可在角色詳細頁的 animation stage 卡片選方向 + Remake。
              </div>
            </div>
          )}

          {/* Object extras */}
          {isObject && (
            <div className="grid grid-cols-2 gap-3">
              {picked.kind === "iso_prop" && (
                <Field label="Size (pixels, single dimension)">
                  <input
                    type="number"
                    min={16}
                    max={128}
                    value={size}
                    onChange={(e) => setSize(parseInt(e.target.value, 10))}
                    className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                  />
                </Field>
              )}
              {(picked.kind === "building" || picked.kind === "iso_building") && (
                <>
                  <Field label="Width (px)">
                    <input
                      type="number"
                      min={32}
                      max={picked.kind === "iso_building" ? 400 : 256}
                      value={width}
                      onChange={(e) => setWidth(parseInt(e.target.value, 10))}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    />
                  </Field>
                  <Field label="Height (px)">
                    <input
                      type="number"
                      min={32}
                      max={picked.kind === "iso_building" ? 400 : 256}
                      value={height}
                      onChange={(e) => setHeight(parseInt(e.target.value, 10))}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    />
                  </Field>
                  <Field label="View">
                    <select
                      value={view}
                      onChange={(e) => setView(e.target.value as CharacterView)}
                      className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                    >
                      {VIEW_OPTIONS.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  {picked.kind === "iso_building" && (
                    <div className="col-span-2 rounded bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
                      <strong>Tip:</strong> pixflux 的 isometric 是 "weakly guiding"。
                      Description 開頭請帶 <code>"isometric pixel art, 30-degree top-down angled view,
                      full building with visible roof and two side walls"</code> 之類字眼,
                      否則 Pixellab 可能還是出立面圖。
                    </div>
                  )}
                </>
              )}
              <Field label="Collision preset">
                <select
                  value={collision}
                  onChange={(e) => setCollision(e.target.value)}
                  className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
                >
                  {COLLISION_OPTIONS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <label className="col-span-2 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={hasCollision}
                  onChange={(e) => setHasCollision(e.target.checked)}
                  className="accent-emerald-500"
                />
                <span>Generate StaticBody2D for collision</span>
              </label>
            </div>
          )}

          {/* Tags */}
          <div className="grid grid-cols-3 gap-3">
            <Field label="Zones (optional, comma-separated)">
              <input
                type="text"
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                placeholder="zone_pharmacy_1983, zone_market_1983"
                className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Category (optional)">
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="vendor"
                className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Chapter (optional)">
              <input
                type="text"
                value={chapter}
                onChange={(e) => setChapter(e.target.value)}
                placeholder="1"
                className="w-full rounded bg-stone-800 px-3 py-2 text-sm"
              />
            </Field>
          </div>

          {error && (
            <div className="rounded bg-red-900/30 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}
        </div>

        <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-stone-800 bg-stone-900 px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-stone-800 px-4 py-2 text-sm hover:bg-stone-700"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={submitting || !name.trim()}
            className="rounded bg-emerald-700 px-4 py-2 text-sm text-emerald-50 hover:bg-emerald-600 disabled:bg-stone-700 disabled:text-stone-500"
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold text-stone-400">
        {label}
      </label>
      {children}
    </div>
  )
}
