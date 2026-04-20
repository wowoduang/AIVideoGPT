// src/types/api.ts

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled';

export interface User {
  id: string;
  email: string;
  username: string;
}

export interface Job {
  task_id: string;
  status: TaskStatus;
  progress: number;
  type: string;
  created_at: string;
  updated_at: string;
  result?: {
    videos?: string[];
    combined_videos?: string[];
    task_dir?: string;
    error?: string;
  };
}

export interface WorkspaceInfo {
  root: string;
  storage: string;
  logs: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ApiError {
  detail: string | Array<{ msg: string; loc: string[] }>;
}
