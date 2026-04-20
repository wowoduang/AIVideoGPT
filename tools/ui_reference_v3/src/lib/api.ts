// src/lib/api.ts
import { Job, User, WorkspaceInfo, AuthResponse } from '../types/api';

// @ts-ignore
const BASE_URL = import.meta.env.VITE_LOCAL_API_BASE_URL || 'http://127.0.0.1:18000';
const API_V1 = `${BASE_URL}/api/v1`;

class ApiClient {
  private token: string | null = localStorage.getItem('auth_token');

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_V1}${path}`;
    const headers = new Headers(options.headers);
    
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail));
    }

    return response.json();
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
    }
  }

  // System
  getWorkspace(): Promise<WorkspaceInfo> {
    return this.request<WorkspaceInfo>('/system/workspace');
  }

  // Auth
  async login(data: any): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(res.access_token);
    return res;
  }

  async register(data: any): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(res.access_token);
    return res;
  }

  getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  logout(): Promise<void> {
    this.setToken(null);
    return this.request<void>('/auth/logout', { method: 'POST' });
  }

  getHistory(): Promise<Job[]> {
    return this.request<Job[]>('/auth/jobs');
  }

  // Jobs
  createMovieStoryJob(data: any): Promise<Job> {
    return this.request<Job>('/jobs/movie-story-script', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  createHighlightJob(data: any): Promise<Job> {
    return this.request<Job>('/jobs/highlight-script', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  createVideoJob(data: any): Promise<Job> {
    return this.request<Job>('/jobs/video', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  getJobStatus(taskId: string): Promise<Job> {
    return this.request<Job>(`/jobs/${taskId}`);
  }
}

export const api = new ApiClient();
