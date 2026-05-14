// Web v2 client aligned with api/contract.md.
// It prefers the Phase 3 FastAPI adapter when NEXT_PUBLIC_API_BASE_URL is set,
// and keeps a local mock fallback for backend-less previews.

export type TaskStatus = 'queued' | 'processing' | 'succeeded' | 'failed' | 'expired';
export type Platform = 'web' | 'mobileWeb' | 'wechatMiniapp';
export type AiMode = 'none' | 'preview' | 'enhance';
export type BackgroundColor = 'white' | 'blue' | 'red' | 'gray';

export interface UploadHandle {
  uploadId: string;
  fileId: string;
  filename?: string;
  mimeType: string;
  url?: string;
  expiresAt: string;
}

export interface ResultFile {
  fileId: string;
  previewUrl: string;
  downloadUrl: string;
  expiresAt: string;
}

export interface ApiErrorBody {
  error?: {
    code: string;
    message: string;
    retryable: boolean;
    traceId?: string;
  };
}

export interface ProcessingTask {
  taskId: string;
  status: TaskStatus;
  uploadId: string;
  templateId: string;
  platform: Platform;
  aiMode: AiMode;
  options: {
    background: BackgroundColor;
    renderOfficialIdPhoto: boolean;
    renderAiEnhancePreview: boolean;
    aiEnhancePreviewKind?: 'none' | 'local-derived-preview' | string;
  };
  officialResult?: ResultFile;
  aiEnhanceResult?: ResultFile;
  error?: {
    code: string;
    message: string;
    retryable: boolean;
    traceId?: string;
  };
}

export interface TaskCreateInput {
  uploadId: string;
  templateId: string;
  platform: Platform;
  aiMode: AiMode;
  options?: Record<string, unknown>;
}

export interface IdPhotoTemplate {
  templateId: string;
  label: string;
  size: string;
  headRange: string;
  printNote: string;
  height?: number;
  width?: number;
  dpi?: number;
}

export interface StudioConfig {
  consent: { required: boolean; title: string; body: string };
  privacy: { retentionHours: number; deletionCopy: string };
  uploadLimits?: { maxBytes: number; maxPixels: number; allowedMimeTypes: string[]; allowedExtensions: string[] };
  aiDisclaimer: string;
  copy: { productName: string; uploadCta: string };
  features: { officialIdPhoto: boolean; aiEnhancePreview: boolean; wechatMiniappReady: boolean };
}

export interface AuthState {
  authenticated: boolean;
  username?: string | null;
}

export interface AdminStats {
  phase: string;
  generatedAt: string;
  today: {
    logins: number;
    uploads: number;
    tasksSucceeded: number;
    tasksFailed: number;
    downloads: number;
    rateLimitHits: number;
  };
  last24h: {
    logins: number;
    uploads: number;
    tasksSucceeded: number;
    tasksFailed: number;
    downloads: number;
    rateLimitHits: number;
  };
  runtime: {
    uploadsBytes: number;
    resultsBytes: number;
    uploadsTracked: number;
    tasksTracked: number;
  };
  recentErrorCodesTop: { code: string; count: number }[];
  rateLimits: {
    uploadsPerMinute: number;
    tasksPerMinute: number;
    loginPerMinute: number;
    storage: string;
  };
}

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? '').replace(/\/$/, '');
const useMockApi = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true' || !apiBaseUrl;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const stamp = () => Math.random().toString(36).slice(2, 8);
const expiresAt = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString();

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { credentials: 'include', ...init });
  if (!response.ok) {
    let apiMessage = `API ${init?.method ?? 'GET'} ${path} failed: ${response.status}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.error?.message) {
        apiMessage = `${body.error.code}: ${body.error.message}`;
      }
    } catch {
      // Keep the HTTP fallback message when the error body is not JSON.
    }
    throw new Error(apiMessage);
  }
  return response.json() as Promise<T>;
}

export const templates: IdPhotoTemplate[] = [
  { templateId: 'cn-id-1inch', label: '一寸', size: '25 × 35 mm', headRange: '头顶 3–5 mm · 肩线居中', printNote: '常用报名 / 简历 / 证件归档', height: 413, width: 295, dpi: 300 },
  { templateId: 'cn-id-2inch', label: '二寸', size: '35 × 49 mm', headRange: '脸部 28–33 mm · 留白均衡', printNote: '考试 / 档案 / 纸质冲印', height: 626, width: 413, dpi: 300 },
  { templateId: 'passport-visa', label: '护照 / 签证', size: '33 × 48 mm', headRange: '眼线参考 · ICAO 风格构图', printNote: '护照、签证材料预检', height: 567, width: 390, dpi: 300 },
];

export const config: StudioConfig = {
  consent: {
    required: true,
    title: 'Photo processing consent',
    body: useMockApi
      ? 'Your portrait stays inside this browser mock unless a backend API base URL is configured.'
      : 'Your portrait is uploaded to the Phase 2.5 API adapter and receives expiring file handles.',
  },
  privacy: {
    retentionHours: 6,
    deletionCopy: 'Uploads and generated files expire automatically.',
  },
  uploadLimits: {
    maxBytes: 20 * 1024 * 1024,
    maxPixels: 24_000_000,
    allowedMimeTypes: ['image/jpeg', 'image/png', 'image/webp'],
    allowedExtensions: ['.jpg', '.jpeg', '.png', '.webp'],
  },
  aiDisclaimer: 'AI enhance is optional and visually separated from official ID photo output.',
  copy: { productName: 'HivisionIDPhotos Studio', uploadCta: 'Select portrait' },
  features: { officialIdPhoto: true, aiEnhancePreview: true, wechatMiniappReady: true },
};

async function mockCreateUpload(file: File): Promise<UploadHandle> {
  await wait(260);
  return {
    uploadId: `upl_mock_${stamp()}`,
    fileId: `file_source_${stamp()}`,
    filename: file.name,
    mimeType: file.type || 'image/jpeg',
    expiresAt: expiresAt(60),
  };
}

async function mockCreateTask(input: TaskCreateInput): Promise<ProcessingTask> {
  await wait(240);
  const background = (input.options?.background ?? 'white') as BackgroundColor;
  const renderAiEnhancePreview = input.aiMode === 'preview' || input.aiMode === 'enhance';
  return {
    taskId: `task_mock_${stamp()}`,
    status: 'queued',
    uploadId: input.uploadId,
    templateId: input.templateId,
    platform: input.platform,
    aiMode: input.aiMode,
    options: {
      background,
      renderOfficialIdPhoto: true,
      renderAiEnhancePreview,
      aiEnhancePreviewKind: renderAiEnhancePreview ? 'local-derived-preview' : 'none',
    },
  };
}

async function mockGetTask(task: ProcessingTask, tick: number): Promise<ProcessingTask> {
  await wait(180);
  if (tick <= 0) return { ...task, status: 'queued' };
  if (tick === 1) return { ...task, status: 'processing' };

  const officialResult: ResultFile = {
    fileId: `file_result_official_${task.taskId.slice(-6)}`,
    previewUrl: '#mock-official-preview-miniapp-compatible',
    downloadUrl: '#mock-official-download-miniapp-compatible',
    expiresAt: expiresAt(90),
  };

  return {
    ...task,
    status: 'succeeded',
    officialResult,
    aiEnhanceResult: task.options.renderAiEnhancePreview
      ? {
          fileId: `file_result_ai_${task.taskId.slice(-6)}`,
          previewUrl: '#mock-ai-preview-separated',
          downloadUrl: '#mock-ai-download-separated',
          expiresAt: expiresAt(90),
        }
      : undefined,
  };
}

export async function login(username: string, password: string): Promise<AuthState> {
  if (useMockApi) {
    await wait(120);
    return { authenticated: true, username };
  }
  return requestJson<AuthState>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
}

export async function getAuthState(): Promise<AuthState> {
  if (useMockApi) {
    await wait(80);
    return { authenticated: false };
  }
  return requestJson<AuthState>('/api/auth/me');
}

export async function logout(): Promise<AuthState> {
  if (useMockApi) {
    await wait(80);
    return { authenticated: false };
  }
  return requestJson<AuthState>('/api/auth/logout', { method: 'POST' });
}

export async function createUpload(file: File): Promise<UploadHandle> {
  if (useMockApi) return mockCreateUpload(file);

  const formData = new FormData();
  formData.append('file', file);
  return requestJson<UploadHandle>('/api/uploads', {
    method: 'POST',
    body: formData,
  });
}

export async function createTask(input: TaskCreateInput): Promise<ProcessingTask> {
  if (useMockApi) return mockCreateTask(input);

  return requestJson<ProcessingTask>('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export async function getTask(task: ProcessingTask, tick = 0): Promise<ProcessingTask> {
  if (useMockApi) return mockGetTask(task, tick);

  return requestJson<ProcessingTask>(`/api/tasks/${task.taskId}`);
}

export async function getConfig() {
  if (useMockApi) {
    await wait(80);
    return config;
  }

  return requestJson<StudioConfig>('/api/config');
}

export async function getAdminStats(): Promise<AdminStats> {
  if (useMockApi) {
    await wait(80);
    return {
      phase: '5D',
      generatedAt: new Date().toISOString(),
      today: { logins: 1, uploads: 0, tasksSucceeded: 0, tasksFailed: 0, downloads: 0, rateLimitHits: 0 },
      last24h: { logins: 1, uploads: 0, tasksSucceeded: 0, tasksFailed: 0, downloads: 0, rateLimitHits: 0 },
      runtime: { uploadsBytes: 0, resultsBytes: 0, uploadsTracked: 0, tasksTracked: 0 },
      recentErrorCodesTop: [],
      rateLimits: { uploadsPerMinute: 10, tasksPerMinute: 10, loginPerMinute: 10, storage: 'in-process' },
    };
  }

  return requestJson<AdminStats>('/api/admin/stats');
}

export async function getTemplates() {
  if (useMockApi) {
    await wait(80);
    return templates;
  }

  return requestJson<IdPhotoTemplate[]>('/api/templates');
}
