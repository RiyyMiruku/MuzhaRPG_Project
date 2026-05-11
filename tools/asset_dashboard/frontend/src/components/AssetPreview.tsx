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
  const hasSpritesheet =
    asset.asset_type === "character" &&
    asset.completed_stages.includes("compile_spritesheet")

  return hasSpritesheet ? (
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
      <div className="flex max-h-[60vh] items-center justify-center overflow-auto bg-stone-950 p-4">
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
              width: naturalSize ? naturalSize.w * zoom : "auto",
              height: naturalSize ? naturalSize.h * zoom : "auto",
            }}
            onError={() => setBroken(true)}
            onLoad={(e) => {
              const img = e.currentTarget
              setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
            }}
            className="border border-stone-800"
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
  const [animationType, setAnimationType] = useState<AnimationType>("walk")
  const [direction, setDirection] = useState<string>("south")
  const [zoom, setZoom] = useState(4)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Load atlas + sheet
  useEffect(() => {
    let cancelled = false
    setAtlas(null)
    setImage(null)
    setError(null)

    const png = `/api/asset/file?p=${encodeURIComponent(
      `game/assets/textures/characters/${characterName}.png`
    )}`
    const json = `/api/asset/file?p=${encodeURIComponent(
      `game/assets/textures/characters/${characterName}.json`
    )}`

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
                {ANIMATION_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
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
      <div className="flex max-h-[60vh] justify-center overflow-auto bg-stone-950 p-4">
        {atlas && image ? (
          <canvas
            ref={canvasRef}
            style={{ imageRendering: "pixelated" }}
            className="border border-stone-800"
          />
        ) : (
          <p className="text-sm text-stone-500">Loading sprite…</p>
        )}
      </div>
    </div>
  )
}
