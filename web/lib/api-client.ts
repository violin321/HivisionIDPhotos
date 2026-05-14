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
  aiDisclaimer: string;
  copy: { productName: string; uploadCta: string };
  features: { officialIdPhoto: boolean; aiEnhancePreview: boolean; wechatMiniappReady: boolean };
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
  const response = await fetch(apiUrl(path), init);
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
    retentionHours: 24,
    deletionCopy: 'Uploads and generated files expire automatically.',
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
  await wait(80);
  return config;
}

export async function getTemplates() {
  if (useMockApi) {
    await wait(80);
    return templates;
  }

  return requestJson<IdPhotoTemplate[]>('/api/templates');
}
