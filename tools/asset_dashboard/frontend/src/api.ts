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
    prompt?: string
  ): Promise<{ job_id: string; stage: string }> {
    return jsonFetch(`/api/asset/${assetType}/${encodeURIComponent(name)}/remake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, prompt }),
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
}
