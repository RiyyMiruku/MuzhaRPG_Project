import type { AssetType, CreateAssetBody, JobInfo, ManifestResponse, StageDetail } from "./types"

const BASE = ""

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + url, init)
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json() as Promise<T>
}

export const api = {
  manifest(): Promise<ManifestResponse> {
    return jsonFetch<ManifestResponse>("/api/manifest")
  },

  thumbnailUrl(assetType: AssetType, name: string): string {
    return `${BASE}/api/asset/${assetType}/${encodeURIComponent(name)}/thumbnail`
  },

  async patchPrompt(
    assetType: AssetType,
    name: string,
    stage: string,
    prompt: string
  ): Promise<void> {
    await jsonFetch(`/api/asset/${assetType}/${encodeURIComponent(name)}/prompts`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, prompt }),
    })
  },

  async remake(
    assetType: AssetType,
    name: string,
    stage: string,
    prompt?: string,
    directions?: string[]
  ): Promise<{ job_id?: string; stage: string }> {
    // v2 character animation/import stages live under a different REST path
    // (no subprocess; worker re-dispatches in-process). Route there for the
    // known v2 stage names. `prompt` is ignored for template-mode v2 stages.
    const V2_CHARACTER_STAGES = new Set([
      "generate_rotations", "animate_idle", "animate_walk", "import_to_godot",
    ])
    if (assetType === "character" && V2_CHARACTER_STAGES.has(stage)) {
      const body: Record<string, unknown> = {}
      if (directions && directions.length > 0) body.directions = directions
      return jsonFetch(
        `/api/v2/asset/character/${encodeURIComponent(name)}/stage/${encodeURIComponent(stage)}/retry`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      )
    }
    // Legacy subprocess path (object/tileset assets, legacy character entries).
    const body: Record<string, unknown> = { stage }
    if (prompt !== undefined) body.prompt = prompt
    if (directions && directions.length > 0) body.directions = directions
    return jsonFetch(`/api/asset/${assetType}/${encodeURIComponent(name)}/remake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  },

  jobs(): Promise<{ jobs: JobInfo[] }> {
    return jsonFetch("/api/jobs")
  },

  jobDetail(jobId: string): Promise<JobInfo> {
    return jsonFetch(`/api/jobs/${jobId}`)
  },

  stage(assetType: AssetType, name: string, stage: string): Promise<StageDetail> {
    return jsonFetch<StageDetail>(
      `/api/asset/${assetType}/${encodeURIComponent(name)}/stage/${encodeURIComponent(stage)}`
    )
  },

  create(body: CreateAssetBody): Promise<{ job_id: string; asset_name: string; asset_type: string }> {
    return jsonFetch("/api/asset/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  },

  async deleteAsset(
    assetType: AssetType,
    name: string
  ): Promise<{ deleted: string; deleted_files: string[]; file_errors: string[] }> {
    return jsonFetch(`/api/asset/${assetType}/${encodeURIComponent(name)}`, {
      method: "DELETE",
    })
  },

  /** Overwrite an existing image file under art_source/ or game/. The path
   *  must already exist; backend refuses to create new files via this route.
   *  Used by the pixel editor to write back edited PNG bytes. */
  async writeFile(repoPath: string, blob: Blob): Promise<{ bytes_written: number }> {
    const url = `${BASE}/api/asset/file?p=${encodeURIComponent(repoPath)}`
    const r = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": blob.type || "application/octet-stream" },
      body: blob,
    })
    if (!r.ok) throw new Error(`PUT ${url} → ${r.status}: ${await r.text()}`)
    return r.json()
  },

  async deleteJob(jobId: string): Promise<void> {
    await jsonFetch(`/api/jobs/${jobId}`, { method: "DELETE" })
  },

  async clearFinishedJobs(): Promise<{ removed_count: number }> {
    return jsonFetch("/api/jobs", { method: "DELETE" })
  },
}
