import { createClient } from '@metagptx/web-sdk';
import { config } from './config';

export const client = createClient();

export type SubtitleLine = {
  id: number;
  start: string;
  end: string;
  text: string;
};

export type JobAcceptedResponse = {
  task_id: string;
  job_type: string;
  status: string;
  progress: number;
  task_dir: string;
};

export type JobStatusResponse = {
  task_id: string;
  job_type: string;
  status: string;
  state: number;
  progress: number;
  message?: string;
  error?: string;
  task_dir?: string;
  videos?: string[];
  combined_videos?: string[];
  is_running?: boolean;
  payload?: Record<string, any>;
};

export type UploadResponse = {
  path: string;
  filename: string;
  size: number;
  kind: 'video' | 'subtitle';
};

export type MovieStoryRequest = {
  video_path: string;
  subtitle_path?: string;
  video_theme?: string;
  narration_style?: string;
  generation_mode?: string;
  visual_mode?: string;
  target_duration_minutes?: number;
  highlight_only?: boolean;
  asr_backend?: string;
};

export type VideoGenerationParams = {
  video_clip_json?: any[];
  video_clip_json_path?: string;
  video_origin_path: string;
  video_aspect: string;
  voice_name: string;
  voice_rate: number;
  voice_pitch?: number;
  tts_engine?: string;
  subtitle_enabled: boolean;
  font_name: string;
  font_size: number;
  text_fore_color?: string;
  stroke_color?: string;
  stroke_width?: number;
  subtitle_position?: string;
  custom_position?: number;
  bgm_name?: string;
  bgm_type?: string;
  n_threads?: number;
};

function withBase(path: string) {
  const base = config.API_BASE_URL || '';
  if (!base) return path;
  return `${base.replace(/\/$/, '')}${path}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const body = isJson ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof body === 'string' ? body : body?.detail || body?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(withBase(path), {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers || {}),
    },
  });
  return parseResponse<T>(response);
}

export async function uploadVideo(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  return requestJson<UploadResponse>('/api/v1/uploads/video', { method: 'POST', body: form });
}

export async function uploadSubtitle(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  return requestJson<UploadResponse>('/api/v1/uploads/subtitle', { method: 'POST', body: form });
}

export async function readSubtitleLines(path: string): Promise<SubtitleLine[]> {
  const url = `/api/v1/uploads/subtitle-content?path=${encodeURIComponent(path)}`;
  return requestJson<SubtitleLine[]>(url, { method: 'GET' });
}

export async function createMovieStoryJob(request: MovieStoryRequest): Promise<JobAcceptedResponse> {
  return requestJson<JobAcceptedResponse>('/api/v1/jobs/movie-story-script', {
    method: 'POST',
    body: JSON.stringify({
      request: {
        video_path: request.video_path,
        subtitle_path: request.subtitle_path || '',
        video_theme: request.video_theme || '',
        narration_style: request.narration_style || 'general',
        generation_mode: request.generation_mode || 'balanced',
        visual_mode: request.visual_mode || 'auto',
        target_duration_minutes: request.target_duration_minutes || 8,
        highlight_only: Boolean(request.highlight_only),
        asr_backend: request.asr_backend || 'qwen3.6-plus',
        cache_mode: 'clear_and_regenerate',
      },
    }),
  });
}

export async function createVideoJob(params: VideoGenerationParams): Promise<JobAcceptedResponse> {
  return requestJson<JobAcceptedResponse>('/api/v1/jobs/video', {
    method: 'POST',
    body: JSON.stringify({ params }),
  });
}

export async function getJobStatus(taskId: string): Promise<JobStatusResponse> {
  return requestJson<JobStatusResponse>(`/api/v1/jobs/${taskId}`, { method: 'GET' });
}

export async function waitForJob(
  taskId: string,
  options?: {
    intervalMs?: number;
    timeoutMs?: number;
    onTick?: (snapshot: JobStatusResponse) => void;
  }
): Promise<JobStatusResponse> {
  const intervalMs = options?.intervalMs ?? 2000;
  const timeoutMs = options?.timeoutMs ?? 1000 * 60 * 30;
  const startedAt = Date.now();

  while (true) {
    const snapshot = await getJobStatus(taskId);
    options?.onTick?.(snapshot);

    if (snapshot.status === 'complete' || snapshot.state === 1) {
      return snapshot;
    }
    if (snapshot.status === 'failed' || snapshot.state === -1) {
      throw new Error(snapshot.error || snapshot.message || '任务执行失败');
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error('任务等待超时');
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export function extractMovieStoryArtifacts(snapshot: JobStatusResponse): {
  subtitlePath: string;
  scriptPath: string;
  scriptItems: any[];
} {
  const payload = snapshot.payload || {};
  const result = (payload.result || {}) as Record<string, any>;

  return {
    subtitlePath:
      String(
        result.subtitle_path ||
          result.subtitle_file ||
          payload.subtitle_path ||
          ''
      ) || '',
    scriptPath:
      String(
        result.video_clip_json_path ||
          result.script_path ||
          result.output_script_path ||
          payload.video_clip_json_path ||
          ''
      ) || '',
    scriptItems:
      (Array.isArray(result.video_clip_json) && result.video_clip_json) ||
      (Array.isArray(result.script_items) && result.script_items) ||
      (Array.isArray(result.script) && result.script) ||
      (Array.isArray(payload.video_clip_json) && payload.video_clip_json) ||
      [],
  };
}

export function extractVideoOutputs(snapshot: JobStatusResponse): string[] {
  const payload = snapshot.payload || {};
  const result = (payload.result || {}) as Record<string, any>;
  const combined = Array.isArray(snapshot.combined_videos) ? snapshot.combined_videos : [];
  const videos = Array.isArray(snapshot.videos) ? snapshot.videos : [];
  const resultVideos = Array.isArray(result.videos) ? result.videos : [];
  const outputPath = result.output_video_path ? [String(result.output_video_path)] : [];
  return [...combined, ...videos, ...resultVideos, ...outputPath].filter(Boolean);
}
