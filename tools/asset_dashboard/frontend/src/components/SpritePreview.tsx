import { useEffect, useMemo, useRef, useState } from "react"

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

interface Props {
  characterName: string
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

const ZOOM = 4

export function SpritePreview({ characterName }: Props) {
  const [atlas, setAtlas] = useState<Atlas | null>(null)
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [animationType, setAnimationType] = useState<AnimationType>("walk")
  const [direction, setDirection] = useState<string>("south")
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Load atlas + image
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

  // Available directions for the current animation type
  const availableDirections = useMemo(() => {
    if (!atlas) return [] as string[]
    return DIRECTION_ORDER.filter((d) => `${animationType}_${d}` in atlas.animations)
  }, [atlas, animationType])

  // If the current direction is unavailable, snap to the first available.
  useEffect(() => {
    if (availableDirections.length === 0) return
    if (!availableDirections.includes(direction)) {
      setDirection(availableDirections[0])
    }
  }, [availableDirections, direction])

  // Animation loop
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
    canvas.width = fw * ZOOM
    canvas.height = fh * ZOOM
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
        fw * ZOOM,
        fh * ZOOM
      )
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(raf)
  }, [atlas, image, animationType, direction])

  if (error) {
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-900/20 p-4 text-sm text-red-300">
        Sprite preview unavailable: {error}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-stone-400">Animation:</span>
          <select
            className="rounded bg-stone-800 px-2 py-1"
            value={animationType}
            onChange={(e) => setAnimationType(e.target.value as AnimationType)}
          >
            {ANIMATION_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
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
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        {availableDirections.length === 0 && atlas && (
          <span className="text-xs text-stone-500">
            No {animationType} animations exist for this character yet.
          </span>
        )}
      </div>
      <div className="flex justify-center bg-stone-950 p-4">
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
