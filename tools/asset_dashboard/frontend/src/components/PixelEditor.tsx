/**
 * Minimal pixel editor modal — for repairing single frames or sprites.
 *
 *   click            — paint with current color
 *   alt-click        — eyedropper (sample pixel under cursor)
 *   ⌘Z / Ctrl+Z      — undo last stroke
 *   +/- buttons      — zoom (4–32×)
 *   Save             — PUT bytes back to repoPath; image is reloaded after
 *
 * Scope intentionally small: 1px pencil, no fill/select/layers. For more
 * involved edits, export the PNG, edit in Aseprite, copy back over.
 */
import { useEffect, useRef, useState, useCallback } from "react"
import { X, Pipette, Pencil, Save, ZoomIn, ZoomOut, RotateCcw, Eraser } from "lucide-react"
import { api } from "../api"

interface FrameTarget {
  /** Spritesheet path the frame belongs to. */
  sheet_path: string
  row: number
  col: number
}

interface Props {
  /** URL the editor loads from (browser src). */
  imageUrl: string
  /** Repo-relative path the editor writes back to via PUT /api/asset/file.
   *  Ignored when `frameTarget` is set — frame edits PUT to /sheet-frame. */
  repoPath: string
  /** When present, save writes back to a single (row, col) frame inside a
   *  spritesheet via PUT /api/asset/sheet-frame instead of overwriting a
   *  standalone PNG file. */
  frameTarget?: FrameTarget
  onClose: () => void
  onSaved?: () => void
}

type Tool = "pencil" | "eyedropper" | "eraser"

const MIN_ZOOM = 4
const MAX_ZOOM = 32
const PALETTE_LIMIT = 12

function rgbaToHex(r: number, g: number, b: number, a: number): string {
  const h = (n: number) => n.toString(16).padStart(2, "0")
  return a < 255 ? `#${h(r)}${h(g)}${h(b)}${h(a)}` : `#${h(r)}${h(g)}${h(b)}`
}

function hexToRgba(hex: string): [number, number, number, number] {
  const s = hex.replace("#", "")
  const n = parseInt(s.slice(0, 2), 16)
  const r = n
  const g = parseInt(s.slice(2, 4), 16)
  const b = parseInt(s.slice(4, 6), 16)
  const a = s.length >= 8 ? parseInt(s.slice(6, 8), 16) : 255
  return [r, g, b, a]
}

export function PixelEditor({ imageUrl, repoPath, frameTarget, onClose, onSaved }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [tool, setTool] = useState<Tool>("pencil")
  const [color, setColor] = useState<string>("#ff00ff")
  const [palette, setPalette] = useState<string[]>([])
  const [zoom, setZoom] = useState(8)
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  // Single-level undo: snapshot before each stroke so ⌘Z restores pre-stroke.
  const undoStack = useRef<ImageData[]>([])
  // Where the cursor is over the canvas, in image-space pixels. Drives
  // the brush-preview overlay so the user sees which pixel they'll paint
  // before clicking. null = cursor outside canvas.
  const [hoverPx, setHoverPx] = useState<{ x: number; y: number } | null>(null)

  // Load image once into canvas at 1:1, then CSS scales by `zoom`.
  useEffect(() => {
    const img = new Image()
    img.crossOrigin = "anonymous"
    img.onload = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      const ctx = canvas.getContext("2d")
      if (!ctx) return
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(img, 0, 0)
      setSize({ w: img.naturalWidth, h: img.naturalHeight })
      undoStack.current = []   // fresh load → no undo history
      setDirty(false)
      setErr(null)
    }
    img.onerror = () => setErr(`failed to load ${imageUrl}`)
    img.src = imageUrl
  }, [imageUrl])

  const pickAt = useCallback((x: number, y: number) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return
    const data = ctx.getImageData(x, y, 1, 1).data
    const hex = rgbaToHex(data[0], data[1], data[2], data[3])
    setColor(hex)
    setPalette((prev) => {
      const without = prev.filter((c) => c !== hex)
      return [hex, ...without].slice(0, PALETTE_LIMIT)
    })
  }, [])

  const paintAt = useCallback((x: number, y: number, erase = false) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return
    if (erase) {
      // putImageData ignores composite ops — writing rgba(0,0,0,0) directly
      // overwrites the pixel to fully transparent (true erase, not blend).
      const id = ctx.createImageData(1, 1)
      id.data[0] = 0; id.data[1] = 0; id.data[2] = 0; id.data[3] = 0
      ctx.putImageData(id, x, y)
    } else {
      const [r, g, b, a] = hexToRgba(color)
      const id = ctx.createImageData(1, 1)
      id.data[0] = r; id.data[1] = g; id.data[2] = b; id.data[3] = a
      ctx.putImageData(id, x, y)
    }
    setDirty(true)
  }, [color])

  const onMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!size) return
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * size.w)
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * size.h)
    if (x < 0 || x >= size.w || y < 0 || y >= size.h) return

    if (e.altKey || tool === "eyedropper") {
      pickAt(x, y)
      return
    }
    // Snapshot for undo, then paint.
    const ctx = canvas.getContext("2d")!
    undoStack.current.push(ctx.getImageData(0, 0, size.w, size.h))
    if (undoStack.current.length > 30) undoStack.current.shift()
    paintAt(x, y, tool === "eraser")
  }

  const onMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!size) return
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    const x = Math.floor(((e.clientX - rect.left) / rect.width) * size.w)
    const y = Math.floor(((e.clientY - rect.top) / rect.height) * size.h)
    if (x < 0 || x >= size.w || y < 0 || y >= size.h) {
      setHoverPx(null); return
    }
    setHoverPx({ x, y })
    // Continuous painting while dragging with left button (pencil + eraser).
    if (e.buttons === 1 && (tool === "pencil" || tool === "eraser") && !e.altKey) {
      paintAt(x, y, tool === "eraser")
    }
  }

  const undo = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return
    const prev = undoStack.current.pop()
    if (!prev) return
    ctx.putImageData(prev, 0, 0)
    setDirty(undoStack.current.length > 0)
  }, [])

  // Keyboard: ⌘Z = undo, Esc = close, B/E/I = tool swap
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); undo(); return }
      if (e.key === "Escape") { onClose(); return }
      // Tool hotkeys — skip when typing in any input/textarea.
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === "INPUT" || tag === "TEXTAREA") return
      if (e.key === "b" || e.key === "B") setTool("pencil")
      else if (e.key === "e" || e.key === "E") setTool("eraser")
      else if (e.key === "i" || e.key === "I") setTool("eyedropper")
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [undo, onClose])

  const onSave = async () => {
    const canvas = canvasRef.current
    if (!canvas) return
    setSaving(true); setErr(null)
    try {
      const blob: Blob = await new Promise((resolve, reject) => {
        canvas.toBlob((b) => b ? resolve(b) : reject(new Error("toBlob null")), "image/png")
      })
      if (frameTarget) {
        await api.writeSheetFrame(
          frameTarget.sheet_path, frameTarget.row, frameTarget.col, blob,
        )
      } else {
        await api.writeFile(repoPath, blob)
      }
      setDirty(false)
      undoStack.current = []
      onSaved?.()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !dirty) onClose() }}
    >
      <div className="flex max-h-[90vh] max-w-[90vw] flex-col rounded-lg border border-stone-700 bg-stone-900 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-700 px-4 py-2">
          <span className="font-mono text-xs text-stone-300 truncate" title={frameTarget ? `${frameTarget.sheet_path} · row ${frameTarget.row} col ${frameTarget.col}` : repoPath}>
            {frameTarget
              ? `${frameTarget.sheet_path.split("/").pop()} · row ${frameTarget.row} col ${frameTarget.col}`
              : repoPath}
          </span>
          <button onClick={onClose} className="rounded p-1 hover:bg-stone-800">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3 border-b border-stone-700 px-4 py-2 text-xs">
          <div className="flex gap-1">
            <ToolBtn active={tool === "pencil"} onClick={() => setTool("pencil")} title="Pencil (B)">
              <Pencil className="h-3.5 w-3.5" />
            </ToolBtn>
            <ToolBtn active={tool === "eraser"} onClick={() => setTool("eraser")} title="Eraser — paints fully transparent (E)">
              <Eraser className="h-3.5 w-3.5" />
            </ToolBtn>
            <ToolBtn active={tool === "eyedropper"} onClick={() => setTool("eyedropper")} title="Eyedropper (alt-click or I)">
              <Pipette className="h-3.5 w-3.5" />
            </ToolBtn>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-stone-400">color</span>
            <input
              type="color"
              value={color.length === 9 ? color.slice(0, 7) : color}
              onChange={(e) => setColor(e.target.value)}
              className="h-6 w-10 cursor-pointer rounded border border-stone-700 bg-transparent"
            />
            <code className="rounded bg-stone-800 px-1.5 py-0.5 font-mono text-[10px] text-stone-300">{color}</code>
          </div>
          <div className="flex items-center gap-1">
            {palette.map((c) => (
              <button
                key={c}
                title={c}
                onClick={() => setColor(c)}
                style={{ backgroundColor: c.length === 9 ? c.slice(0, 7) : c }}
                className={"h-5 w-5 rounded border " + (c === color ? "border-emerald-400" : "border-stone-700")}
              />
            ))}
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z / 2))} className="rounded p-1 hover:bg-stone-800" title="Zoom out">
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <span className="w-10 text-center font-mono text-stone-400">{zoom}×</span>
            <button onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z * 2))} className="rounded p-1 hover:bg-stone-800" title="Zoom in">
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
          </div>
          <button onClick={undo} disabled={undoStack.current.length === 0} className="flex items-center gap-1 rounded bg-stone-800 px-2 py-1 hover:bg-stone-700 disabled:opacity-40" title="Undo (⌘Z)">
            <RotateCcw className="h-3 w-3" /> undo ({undoStack.current.length})
          </button>
          <button onClick={onSave} disabled={!dirty || saving} className="ml-auto flex items-center gap-1 rounded bg-emerald-700 px-3 py-1 text-emerald-50 hover:bg-emerald-600 disabled:bg-stone-700 disabled:text-stone-500" title="Save back (PUT)">
            <Save className="h-3 w-3" /> {saving ? "saving…" : dirty ? "save" : "saved"}
          </button>
        </div>

        {/* Canvas area */}
        <div className="flex-1 overflow-auto bg-[repeating-conic-gradient(#202020_0_25%,#181818_0_50%)] bg-[length:16px_16px] p-4">
          <div className="relative inline-block">
            <canvas
              ref={canvasRef}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseLeave={() => setHoverPx(null)}
              style={{
                imageRendering: "pixelated",
                width: size ? `${size.w * zoom}px` : undefined,
                height: size ? `${size.h * zoom}px` : undefined,
                cursor: tool === "eyedropper" ? "crosshair" : "crosshair",
                display: "block",
              }}
            />
            {/* Brush preview overlay: a 1-pixel square at the hovered position,
                scaled by zoom. Color matches current paint color so the user
                sees exactly what + where they're about to write. For the
                eyedropper, we still highlight (with a dashed outline) so
                they know which pixel they'll sample. */}
            {hoverPx && size && (
              <div
                className={"pointer-events-none absolute " +
                  (tool === "eyedropper"
                    ? "border border-dashed border-white"
                    : tool === "eraser"
                      ? "border border-dashed border-red-400"
                      : "border border-white/80")}
                style={{
                  left: `${hoverPx.x * zoom}px`,
                  top: `${hoverPx.y * zoom}px`,
                  width: `${zoom}px`,
                  height: `${zoom}px`,
                  backgroundColor: tool === "pencil"
                    ? (color.length === 9 ? color.slice(0, 7) : color)
                    : "transparent",
                  opacity: tool === "pencil" ? 0.7 : 1,
                  boxShadow: "0 0 0 1px rgba(0,0,0,0.6)",
                }}
              />
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-stone-700 px-4 py-1.5 text-[10px] text-stone-500">
          <span>
            {size && `${size.w}×${size.h}px`}
            {dirty && <span className="ml-2 text-amber-400">● unsaved</span>}
          </span>
          <span>B = pencil · E = eraser · I/alt-click = eyedropper · ⌘Z = undo · esc = close</span>
        </div>
        {err && <div className="border-t border-red-900/60 bg-red-900/20 px-4 py-1.5 text-xs text-red-300">{err}</div>}
      </div>
    </div>
  )
}

function ToolBtn(props: { active: boolean; onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button
      onClick={props.onClick}
      title={props.title}
      className={"rounded p-1.5 " + (props.active ? "bg-emerald-700 text-emerald-50" : "bg-stone-800 hover:bg-stone-700")}
    >
      {props.children}
    </button>
  )
}
