import { useEffect, useMemo, useRef, useState } from "react"
import { ImageOff } from "lucide-react"
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
}

/** Top-of-detail preview. For characters that have a compiled spritesheet,
 *  shows an animated canvas player. For everything else (and for characters
 *  pre-spritesheet), shows the static thumbnail. Both support a zoom slider. */
export function AssetPreview({ asset }: Props) {
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
    <AnimatedPreview characterName={asset.name} />
  ) : (
    <StaticPreview asset={asset} />
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

function StaticPreview({ asset }: { asset: AssetSummary }) {
  const [zoom, setZoom] = useState(4)
  const [broken, setBroken] = useState(false)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)
  const url = api.thumbnailUrl(asset.asset_type, asset.name)

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

function AnimatedPreview({ characterName }: { characterName: string }) {
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
  }, [characterName])

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
            <label className="flex items-center gap-2">
              <span className="text-stone-400">Direction:</span>
              <select
                className="rounded bg-stone-800 px-2 py-1"
                value={direction}
                onChange={(e) => setDirection(e.target.value)}
                disabled={availableDirections.length === 0}
              >
                {availableDirections.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            {availableDirections.length === 0 && atlas && (
              <span className="text-xs text-stone-500">
                No {animationType} animations for this character yet.
              </span>
            )}
          </>
        }
      />
      <div className="flex max-h-[60vh] items-start justify-center overflow-auto bg-stone-950 p-4">
        {atlas && image ? (
          <canvas
            ref={canvasRef}
            style={{
              imageRendering: "pixelated",
              // Explicit CSS dimensions match the drawing buffer so flex
              // can't stretch us beyond the intended pixel-art scale.
              width: `${atlas.frame_size[0] * zoom}px`,
              height: `${atlas.frame_size[1] * zoom}px`,
            }}
            className="shrink-0 border border-stone-800"
          />
        ) : (
          <p className="text-sm text-stone-500">Loading sprite…</p>
        )}
      </div>
    </div>
  )
}
