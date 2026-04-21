// Local-only project store that mirrors narratoai.cn's project model.
// The existing Python backend in this repo exposes upload / job APIs but no
// real projects CRUD, so we keep the UI self-contained via localStorage.

export type ProjectStatus = 'draft' | 'completed' | 'exported';

export type ScriptItem = {
  id: string;
  startTime: string;
  endTime: string;
  originalSubtitle: string;
  narration: string;
};

export type ProjectStep = 'upload' | 'config' | 'generate';

export type Project = {
  id: string;
  name: string;
  status: ProjectStatus;
  thumbnailUrl?: string;
  videoUrl?: string;
  videoFileName?: string;
  videoDurationSec?: number;
  createdAt: string;
  updatedAt: string;
  currentStep: ProjectStep;
  config?: {
    llmProvider?: string;
    llmModel?: string;
    ttsProvider?: string;
    ttsVoice?: string;
    style?: string;
    aspectRatio?: string;
  };
  scriptItems?: ScriptItem[];
};

const STORAGE_KEY = 'aivideogpt_projects';
const ACTIVITY_KEY = 'aivideogpt_activities';

export type Activity = {
  id: string;
  kind: 'publish' | 'comment' | 'update';
  title: string;
  at: string;
};

function readAll(): Project[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as Project[];
  } catch {
    return [];
  }
}

function writeAll(items: Project[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new Event('aivideogpt:projects'));
  } catch {
    /* ignore */
  }
}

function uid() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return 'p-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function listProjects(): Project[] {
  return readAll().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getProject(id: string): Project | undefined {
  return readAll().find((p) => p.id === id);
}

export function createProject(name: string): Project {
  const now = new Date().toISOString();
  const project: Project = {
    id: uid(),
    name: name.trim() || '未命名项目',
    status: 'draft',
    createdAt: now,
    updatedAt: now,
    currentStep: 'upload',
  };
  const items = readAll();
  items.unshift(project);
  writeAll(items);
  return project;
}

export function updateProject(id: string, patch: Partial<Project>): Project | undefined {
  const items = readAll();
  const idx = items.findIndex((p) => p.id === id);
  if (idx === -1) return undefined;
  const next: Project = {
    ...items[idx],
    ...patch,
    updatedAt: new Date().toISOString(),
  };
  items[idx] = next;
  writeAll(items);
  return next;
}

export function deleteProject(id: string) {
  const items = readAll().filter((p) => p.id !== id);
  writeAll(items);
}

const SAMPLE_ACTIVITIES: Activity[] = [
  { id: 'a1', kind: 'publish', title: '项目"寂静回声"成功发布', at: '2小时前' },
  { id: 'a2', kind: 'comment', title: '「往昔私语」收到新评论', at: '1天前' },
  { id: 'a3', kind: 'update', title: '项目「明日之影」已更新', at: '3天前' },
];

export function listActivities(): Activity[] {
  try {
    const raw = localStorage.getItem(ACTIVITY_KEY);
    if (raw) return JSON.parse(raw) as Activity[];
  } catch {
    /* ignore */
  }
  return SAMPLE_ACTIVITIES;
}

export function seedSampleProjectsIfEmpty() {
  const items = readAll();
  if (items.length > 0) return;
  const now = new Date();
  const minus = (h: number) =>
    new Date(now.getTime() - h * 3600 * 1000).toISOString();
  const seed: Project[] = [
    {
      id: uid(),
      name: '大明王朝 · 开场解说',
      status: 'draft',
      thumbnailUrl:
        'https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&w=640&q=60',
      createdAt: minus(48),
      updatedAt: minus(3),
      currentStep: 'upload',
    },
    {
      id: uid(),
      name: '一代妖后 · 第 1 集',
      status: 'completed',
      thumbnailUrl:
        'https://images.unsplash.com/photo-1510325594980-6b6e5f3c88a5?auto=format&fit=crop&w=640&q=60',
      createdAt: minus(240),
      updatedAt: minus(168),
      currentStep: 'generate',
    },
    {
      id: uid(),
      name: '镖人 · 预告片',
      status: 'exported',
      thumbnailUrl:
        'https://images.unsplash.com/photo-1502920917128-1aa500764cbd?auto=format&fit=crop&w=640&q=60',
      createdAt: minus(720),
      updatedAt: minus(24),
      currentStep: 'generate',
    },
  ];
  writeAll(seed);
}
