/**
 * Lightweight on-hover animation player for the asset grid.
 *
 * Lazy-loads the spritesheet + atlas the first time the parent says
 * `play === true`, caches both in state, then runs a raf loop while
 * playing. When `play` flips false the loop stops but cached assets
 * stay so re-hovering is instant.
 *
 * Picks the first available animation in priority order:
 *   v2 names → animate_idle, animate_walk
 *   legacy   → add_idle_animation (idle_*), add_walk_animation (walk_*)
 * and the first available direction (south preferred).
 */
import { useEffect, useRef, useState } from "react"

interface AtlasAnimation {
  row: number
  start: number
  end: number
  fps: number
  loop: boolean
}
interface Atlas {
  frame_size: [number, number]
  animations: Record<string, AtlasAnimation>
}

interface Props {
  characterName: string
  play: boolean
}

const ACTION_PRIORITY = ["idle", "walk"] as const
const DIRECTION_PRIORITY = ["south", "south-east", "east", "north"]

export function HoverSpritePreview({ characterName, play }: Props) {
  const [atlas, setAtlas] = useState<Atlas | null>(null)
  const [image, setImage] = useState<HTMLImageElement | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Lazy load on first play. Cache after first load so subsequent hovers
  // are instant (no flash of static thumbnail while atlas re-fetches).
  useEffect(() => {
    if (!play || atlas || loadFailed) return
    let cancelled = false
    // Cache-bust by mount time so a regen doesn't show stale frames.
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
      .then((a) => !cancelled && setAtlas(a))
      .catch(() => !cancelled && setLoadFailed(true))

    const img = new Image()
    img.onload = () => !cancelled && setImage(img)
    img.onerror = () => !cancelled && setLoadFailed(true)
    img.src = png

    return () => {
      cancelled = true
    }
  }, [play, characterName, atlas, loadFailed])

  // Pick first available (action, direction) pair from atlas keys.
  const pick = (() => {
    if (!atlas) return null
    for (const action of ACTION_PRIORITY) {
      for (const dir of DIRECTION_PRIORITY) {
        const key = `${action}_${dir}`
        if (key in atlas.animations) return { action, dir, key }
      }
      // No preferred direction → take any direction this action ships.
      const anyKey = Object.keys(atlas.animations).find((k) => k.startsWith(`${action}_`))
      if (anyKey) {
        return { action, dir: anyKey.slice(action.length + 1), key: anyKey }
      }
    }
    return null
  })()

  // Draw + animate while playing. Dependencies include atlas/image so the
  // loop kicks in the moment lazy-load completes (even mid-hover).
  useEffect(() => {
    if (!play || !atlas || !image || !pick) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const anim = atlas.animations[pick.key]
    const [fw, fh] = atlas.frame_size
    // Container is 128 high in AssetCard's thumbnail box; scale to fit.
    // Use integer zoom so the pixels stay crisp.
    const zoom = Math.max(1, Math.floor(112 / fh))
    canvas.width = fw * zoom
    canvas.height = fh * zoom
    ctx.imageSmoothingEnabled = false

    const frameDur = 1000 / anim.fps
    const frameCount = anim.end - anim.start
    let startTs: number | null = null
    let raf = 0
    const tick = (ts: number) => {
      if (startTs === null) startTs = ts
      const elapsed = ts - startTs
      let frameIdx = Math.floor(elapsed / frameDur)
      if (anim.loop) frameIdx = frameIdx % frameCount
      else if (frameIdx >= frameCount) frameIdx = frameCount - 1
      const col = anim.start + frameIdx
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(
        image, col * fw, anim.row * fh, fw, fh, 0, 0, fw * zoom, fh * zoom,
      )
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [play, atlas, image, pick])

  if (loadFailed) return null    // parent will keep showing the static thumb
  if (!atlas || !image || !pick) return null

  return (
    <canvas
      ref={canvasRef}
      className="max-h-full max-w-full"
      style={{ imageRendering: "pixelated" }}
    />
  )
}
