import { useEffect, useMemo, useRef, useState } from "react"
import {
  ImageOff,
  ArrowUp, ArrowDown, ArrowLeft, ArrowRight,
  ArrowUpLeft, ArrowUpRight, ArrowDownLeft, ArrowDownRight,
} from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"

interface AtlasAnimation {
  row: number
  start: number
  end: number
  fps: number
  loop: boolean
}

interface Atlas {
  character_name: string
  frame_size: [number, number]
  animations: Record<string, AtlasAnimation>
}

const ANIMATION_TYPES = ["idle", "walk"] as const
type AnimationType = (typeof ANIMATION_TYPES)[number]

const DIRECTION_ORDER = [
  "south",
  "south-east",
  "east",
  "north-east",
  "north",
  "north-west",
  "west",
  "south-west",
]

interface Props {
  asset: AssetSummary
  /** Bumped by parent (AssetDetail) on pixel-editor save — forces re-fetch
   *  of the sheet PNG/atlas so the preview reflects the edit immediately. */
  refreshKey?: number
}

/** Top-of-detail preview. For characters that have a compiled spritesheet,
 *  shows an animated canvas player. For everything else (and for characters
 *  pre-spritesheet), shows the static thumbnail. Both support a zoom slider. */
export function AssetPreview({ asset, refreshKey }: Props) {
  // Show the animated preview as soon as any animation stage has completed
  // (the sheet starts existing then, even before compile_spritesheet /
  // import_to_godot). The sheet is read straight from art_source/ so users
  // see in-progress work — partial directions display, missing ones are
  // filtered out by the direction dropdown.
  const hasAnyAnimation =
    asset.asset_type === "character" &&
    (asset.completed_stages.includes("add_idle_animation") ||
      asset.completed_stages.includes("add_walk_animation") ||
      asset.completed_stages.includes("compile_spritesheet") ||
      // v2 stage names
      asset.completed_stages.includes("animate_idle") ||
      asset.completed_stages.includes("animate_walk"))

  return hasAnyAnimation ? (
    <AnimatedPreview characterName={asset.name} refreshKey={refreshKey} />
  ) : (
    <StaticPreview asset={asset} refreshKey={refreshKey} />
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Zoom control (shared)
// ─────────────────────────────────────────────────────────────────────────────

interface ZoomBarProps {
  zoom: number
  setZoom: (z: number) => void
  extras?: React.ReactNode
}

function ZoomBar({ zoom, setZoom, extras }: ZoomBarProps) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
      <label className="flex items-center gap-2">
        <span className="text-stone-400">Zoom:</span>
        <input
          type="range"
          min={1}
          max={16}
          step={1}
          value={zoom}
          onChange={(e) => setZoom(parseInt(e.target.value, 10))}
          className="w-40"
        />
        <span className="w-10 text-xs text-stone-500">{zoom}×</span>
      </label>
      {extras}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Static (non-animated) preview — for props, autotiles, or characters pre-spritesheet
// ─────────────────────────────────────────────────────────────────────────────

function StaticPreview({ asset, refreshKey = 0 }: { asset: AssetSummary; refreshKey?: number }) {
  const [zoom, setZoom] = useState(4)
  const [broken, setBroken] = useState(false)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)
  // Append refreshKey as cache-buster so pixel-edit saves are reflected.
  const url = `${api.thumbnailUrl(asset.asset_type, asset.name)}?_=${refreshKey}`

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900 p-4">
      <ZoomBar
        zoom={zoom}
        setZoom={setZoom}
        extras={
          naturalSize && (
            <span className="text-xs text-stone-500">
              source: {naturalSize.w}×{naturalSize.h} px
            </span>
          )
        }
      />
      <div className="flex max-h-[60vh] items-start justify-center overflow-auto bg-stone-950 p-4">
        {broken ? (
          <div className="flex flex-col items-center gap-2 text-stone-600">
            <ImageOff className="h-10 w-10" />
            <span className="text-xs">Preview unavailable (thumbnail 404)</span>
          </div>
        ) : (
          <img
            src={url}
            alt={asset.name}
            style={{
              imageRendering: "pixelated",
              width: naturalSize ? `${naturalSize.w * zoom}px` : "auto",
              height: naturalSize ? `${naturalSize.h * zoom}px` : "auto",
              transform: asset.extra.flip_h ? "scaleX(-1)" : undefined,
            }}
            onError={() => setBroken(true)}
            onLoad={(e) => {
              const img = e.currentTarget
              setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
            }}
            className="shrink-0 border border-stone-800"
          />
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Animated preview — for characters with a spritesheet
// ─────────────────────────────────────────────────────────────────────────────

function AnimatedPreview({ characterName, refreshKey = 0 }: { characterName: string; refreshKey?: number }) {
  const [atlas, setAtlas] = useState<Atlas | null>(null)
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Default to idle: it's the universal animation (every character has it),
  // and 4-dir static NPCs have no walk so defaulting to walk would land on
  // an empty preview and force a manual switch.
  const [animationType, setAnimationType] = useState<AnimationType>("idle")
  const [direction, setDirection] = useState<string>("south")
  const [zoom, setZoom] = useState(4)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Load atlas + sheet
  useEffect(() => {
    let cancelled = false
    setAtlas(null)
    setImage(null)
    setError(null)

    // Read straight from art_source/ (pipeline output) so previews reflect
    // partial pipeline state — works the moment add_idle_animation or
    // add_walk_animation completes, no need to wait for import_to_godot.
    //
    // Cache-buster: backend already sends Cache-Control: no-cache so the
    // browser SHOULD revalidate, but in practice browsers stash <img>-loaded
    // bytes in memory across re-mounts and serve them without revalidating.
    // A per-mount timestamp param guarantees the URL differs after a
    // regen → forces a real fetch. Cheap on a local dev tool.
    const v = Date.now()
    const png = `/api/asset/file?p=${encodeURIComponent(
      `art_source/characters/${characterName}/spritesheet/${characterName}.png`
    )}&_=${v}`
    const json = `/api/asset/file?p=${encodeURIComponent(
      `art_source/characters/${characterName}/spritesheet/${characterName}.json`
    )}&_=${v}`

    fetch(json)
      .then((r) => {
        if (!r.ok) throw new Error(`atlas ${r.status}`)
        return r.json() as Promise<Atlas>
      })
      .then((a) => {
        if (!cancelled) setAtlas(a)
      })
      .catch((e) => !cancelled && setError(`atlas: ${(e as Error).message}`))

    const img = new Image()
    img.onload = () => !cancelled && setImage(img)
    img.onerror = () => !cancelled && setError(`spritesheet failed to load`)
    img.src = png

    return () => {
      cancelled = true
    }
  }, [characterName, refreshKey])

  // Which animation types the atlas actually contains (some characters
  // — 4-dir static NPCs — have idle but not walk).
  const availableTypes = useMemo<AnimationType[]>(() => {
    if (!atlas) return []
    const present = new Set(Object.keys(atlas.animations).map((k) => k.split("_")[0]))
    return ANIMATION_TYPES.filter((t) => present.has(t))
  }, [atlas])

  // If the current selection isn't supported (e.g. atlas has only idle),
  // jump to the first available so the preview never sits blank.
  useEffect(() => {
    if (availableTypes.length === 0) return
    if (!availableTypes.includes(animationType)) {
      setAnimationType(availableTypes[0])
    }
  }, [availableTypes, animationType])

  const availableDirections = useMemo(() => {
    if (!atlas) return [] as string[]
    return DIRECTION_ORDER.filter((d) => `${animationType}_${d}` in atlas.animations)
  }, [atlas, animationType])

  useEffect(() => {
    if (availableDirections.length === 0) return
    if (!availableDirections.includes(direction)) {
      setDirection(availableDirections[0])
    }
  }, [availableDirections, direction])

  useEffect(() => {
    if (!atlas || !image) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const key = `${animationType}_${direction}`
    const anim = atlas.animations[key]
    if (!anim) return

    const [fw, fh] = atlas.frame_size
    canvas.width = fw * zoom
    canvas.height = fh * zoom
    ctx.imageSmoothingEnabled = false

    const frameDurationMs = 1000 / anim.fps
    const frameCount = anim.end - anim.start
    let startTs: number | null = null
    let raf = 0

    const tick = (ts: number) => {
      if (startTs === null) startTs = ts
      const elapsed = ts - startTs
      let frameIdx = Math.floor(elapsed / frameDurationMs)
      if (anim.loop) {
        frameIdx = frameIdx % frameCount
      } else if (frameIdx >= frameCount) {
        frameIdx = frameCount - 1
      }
      const col = anim.start + frameIdx
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(
        image,
        col * fw,
        anim.row * fh,
        fw,
        fh,
        0,
        0,
        fw * zoom,
        fh * zoom
      )
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(raf)
  }, [atlas, image, animationType, direction, zoom])

  if (error) {
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-900/20 p-4 text-sm text-red-300">
        Sprite preview unavailable: {error}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900 p-4">
      <ZoomBar
        zoom={zoom}
        setZoom={setZoom}
        extras={
          <>
            <label className="flex items-center gap-2">
              <span className="text-stone-400">Animation:</span>
              <select
                className="rounded bg-stone-800 px-2 py-1"
                value={animationType}
                onChange={(e) => setAnimationType(e.target.value as AnimationType)}
              >
                {ANIMATION_TYPES.map((t) => {
                  const supported = availableTypes.includes(t)
                  return (
                    <option key={t} value={t} disabled={!supported}>
                      {t}{!supported && " (n/a)"}
                    </option>
                  )
                })}
              </select>
            </label>
            <span className="font-mono text-xs text-stone-500">
              {availableDirections.length > 0 ? `dir: ${direction}` : `No ${animationType} animations yet`}
            </span>
          </>
        }
      />
      <div className="flex max-h-[60vh] items-center justify-center overflow-auto bg-stone-950 p-4">
        {atlas && image ? (
          <DirectionPad
            current={direction}
            available={new Set(availableDirections)}
            onPick={setDirection}
            frameSize={atlas.frame_size}
            zoom={zoom}
          >
            <canvas
              ref={canvasRef}
              style={{
                imageRendering: "pixelated",
                width: `${atlas.frame_size[0] * zoom}px`,
                height: `${atlas.frame_size[1] * zoom}px`,
              }}
              className="shrink-0 border border-stone-800"
            />
          </DirectionPad>
        ) : (
          <p className="text-sm text-stone-500">Loading sprite…</p>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 3×3 directional pad — character in center, arrow buttons around the edge.
// Replaces a dropdown. Disabled slots dim out for animations missing that dir
// (e.g. idle has only 4 cardinals). Also responds to arrow keys.
// ─────────────────────────────────────────────────────────────────────────────

const DIR_BTN_LAYOUT: Array<{ dir: string; Icon: typeof ArrowUp }> = [
  { dir: "north-west", Icon: ArrowUpLeft },
  { dir: "north",      Icon: ArrowUp },
  { dir: "north-east", Icon: ArrowUpRight },
  { dir: "west",       Icon: ArrowLeft },
  // center — empty (the canvas goes here)
  { dir: "east",       Icon: ArrowRight },
  { dir: "south-west", Icon: ArrowDownLeft },
  { dir: "south",      Icon: ArrowDown },
  { dir: "south-east", Icon: ArrowDownRight },
]

// Arrow-key → direction. Plain arrows = cardinals; Shift+arrow = diagonals.
const KEY_DIR_MAP: Record<string, { plain: string; shift: string }> = {
  ArrowUp:    { plain: "north", shift: "north" },
  ArrowDown:  { plain: "south", shift: "south" },
  ArrowLeft:  { plain: "west",  shift: "west" },
  ArrowRight: { plain: "east",  shift: "east" },
}

function DirectionPad({
  current, available, onPick, frameSize, zoom, children,
}: {
  current: string
  available: Set<string>
  onPick: (d: string) => void
  frameSize: [number, number]
  zoom: number
  children: React.ReactNode
}) {
  const [fw, fh] = frameSize
  // Buttons sit ~36px outside the canvas; cell size matches button hit area
  const cellSize = 36

  // Keyboard arrow-key support — only when the pad is mounted.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't hijack when typing in a form field.
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return
      const m = KEY_DIR_MAP[e.key]
      if (!m) return
      const want = m.plain
      if (available.has(want)) {
        e.preventDefault()
        onPick(want)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [available, onPick])

  // CSS grid: 3×3, center cell is the canvas (any size, drives row/col size).
  return (
    <div
      className="grid items-center justify-items-center gap-1.5"
      style={{
        gridTemplateColumns: `${cellSize}px ${fw * zoom}px ${cellSize}px`,
        gridTemplateRows: `${cellSize}px ${fh * zoom}px ${cellSize}px`,
      }}
    >
      {/* Row 0: NW, N, NE */}
      {DIR_BTN_LAYOUT.slice(0, 3).map((b) => (
        <DirBtn key={b.dir} active={current === b.dir} enabled={available.has(b.dir)} onClick={() => onPick(b.dir)} Icon={b.Icon} label={b.dir} />
      ))}
      {/* Row 1: W, [canvas], E */}
      <DirBtn active={current === "west"} enabled={available.has("west")} onClick={() => onPick("west")} Icon={ArrowLeft} label="west" />
      <div className="flex h-full w-full items-center justify-center">{children}</div>
      <DirBtn active={current === "east"} enabled={available.has("east")} onClick={() => onPick("east")} Icon={ArrowRight} label="east" />
      {/* Row 2: SW, S, SE */}
      {DIR_BTN_LAYOUT.slice(5).map((b) => (
        <DirBtn key={b.dir} active={current === b.dir} enabled={available.has(b.dir)} onClick={() => onPick(b.dir)} Icon={b.Icon} label={b.dir} />
      ))}
    </div>
  )
}

function DirBtn({
  active, enabled, onClick, Icon, label,
}: {
  active: boolean
  enabled: boolean
  onClick: () => void
  Icon: typeof ArrowUp
  label: string
}) {
  return (
    <button
      type="button"
      onClick={enabled ? onClick : undefined}
      disabled={!enabled}
      title={enabled ? label : `${label} (not available for this animation)`}
      className={
        "flex h-9 w-9 items-center justify-center rounded border transition-colors " +
        (active
          ? "border-emerald-500 bg-emerald-700 text-emerald-50"
          : enabled
            ? "border-stone-700 bg-stone-800 text-stone-300 hover:border-stone-500 hover:text-stone-100"
            : "border-stone-800 bg-stone-900 text-stone-700 cursor-not-allowed")
      }
    >
      <Icon className="h-4 w-4" />
    </button>
  )
}
