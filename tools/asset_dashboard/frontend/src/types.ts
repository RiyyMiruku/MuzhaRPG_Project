export type AssetType = "character" | "tileset" | "object"

export interface AssetSummary {
  name: string
  asset_type: AssetType
  description: string | null
  tags: string[]
  zone: string | null
  category: string | null
  chapter: string | null
  completed_stages: string[]
  all_stages: string[]
  prompts: Record<string, string>
  png_path: string | null
  progress: string
  extra: Record<string, unknown>
}

export interface ManifestResponse {
  assets: AssetSummary[]
  manifest_path: string
}

export interface JobInfo {
  id: string
  cmd: string[]
  asset_name: string | null
  stage: string | null
  status: "pending" | "running" | "completed" | "failed"
  exit_code: number | null
  started_at: number
  finished_at: number | null
  tail?: string
}

export interface StageImage {
  path: string
  url: string
}

export interface StageDetail {
  stage: string
  completed_at: string | null
  prompt: string | null
  images: StageImage[]
}
