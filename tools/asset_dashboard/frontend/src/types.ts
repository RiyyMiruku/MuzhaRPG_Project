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

export type CharacterKind = "moving" | "static"
export type ObjectKind = "iso_prop" | "building"
export type CharacterView = "high_top_down" | "low_top_down" | "side"
export type Proportions =
  | "cartoon"
  | "chibi"
  | "stylized"
  | "realistic_male"
  | "realistic_female"
  | "heroic"

export interface CreateAssetBody {
  asset_type: AssetType
  kind?: CharacterKind | ObjectKind
  name: string
  description?: string
  zone?: string
  category?: string
  chapter?: string

  // character
  directions?: 4 | 8
  view?: CharacterView
  proportions?: Proportions
  idle_frame_count?: number
  walk_frame_count?: number
  no_idle?: boolean

  // object
  size?: number
  width?: number
  height?: number
  collision?: string
  has_collision?: boolean

  // tileset
  lower?: string
  upper?: string
  transition_size?: number
  transition_description?: string
}
