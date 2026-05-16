// Web v2 client aligned with api/contract.md.
// It prefers the Phase 3 FastAPI adapter when NEXT_PUBLIC_API_BASE_URL is set,
// and keeps a local mock fallback for backend-less previews.

export type TaskStatus = 'queued' | 'processing' | 'succeeded' | 'failed' | 'expired';
export type Platform = 'web' | 'mobileWeb' | 'wechatMiniapp';
export type AiMode = 'none' | 'preview' | 'enhance';
export type AiProMode = 'ai_repair' | 'ai_blue_formal_id_photo' | 'executive_headshot';
export type BackgroundColor = 'white' | 'blue' | 'red' | 'gray';
export type TaskBackgroundColor = BackgroundColor | 'custom';
export type QualityIssueSeverity = 'warning' | 'error';

export interface QualityIssue {
  code: string;
  message: string;
  severity?: QualityIssueSeverity;
  metric?: string;
}

export interface QualityReport {
  score: number;
  passed: boolean;
  metrics: Record<string, unknown>;
  warnings: QualityIssue[];
  errors: QualityIssue[];
  suggestions: string[];
}
export type ImageKbMode = 'exact' | 'max';
export type LayoutPaperSize = 'six-inch' | 'five-inch' | 'a4';
export type RenderMode = 'solid' | 'upDownGradientWhite' | 'centerGradientWhite';

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

export interface AiProRequest {
  enabled: boolean;
  modes: AiProMode[];
  promptParams: {
    backgroundColor?: string;
    outfit?: string;
    expression?: string;
    retouchLevel?: string;
    outputSpec?: string;
    style?: string;
    [key: string]: unknown;
  };
  consentAccepted: boolean;
}

export interface AiProResult {
  mode: AiProMode | string;
  status: string;
  imageUrl?: string | null;
  previewUrl?: string | null;
  downloadUrl?: string | null;
  usageLabel: string;
  promptTemplateId: string;
  templateVersion: string;
  paid: boolean;
  qualityReport?: Record<string, unknown> | null;
  promptMetadata: Record<string, unknown>;
  mock?: boolean;
}

export interface ApiErrorBody {
  error?: {
    code: string;
    message: string;
    retryable: boolean;
    traceId?: string;
  };
  detail?: string | {
    error?: {
      code?: string;
      message?: string;
      retryable?: boolean;
      traceId?: string;
    };
    message?: string;
  };
}

export interface TaskOptions {
  background: TaskBackgroundColor;
  renderOfficialIdPhoto: boolean;
  renderAiEnhancePreview: boolean;
  aiEnhancePreviewKind?: 'none' | 'local-derived-preview' | string;
  humanMattingModel?: string;
  faceDetectModel?: string;
  faceAlign?: boolean;
  headMeasureRatio?: number;
  headHeightRatio?: number;
  topDistance?: number;
  topDistanceMax?: number;
  topDistanceMin?: number;
  dpi?: number;
  whiteningStrength?: number;
  brightnessStrength?: number;
  contrastStrength?: number;
  saturationStrength?: number;
  sharpenStrength?: number;
  imageKb?: number;
  imageKbMode?: ImageKbMode;
  watermarkEnabled?: boolean;
  watermarkText?: string;
  watermarkTextColor?: string;
  watermarkTextSize?: number;
  watermarkTextOpacity?: number;
  watermarkTextAngle?: number;
  watermarkTextSpace?: number;
  printLayoutEnabled?: boolean;
  layoutPaperSize?: LayoutPaperSize;
  printLayoutSize?: LayoutPaperSize;
  layoutCropLine?: boolean;
  horizontalFlip?: boolean;
  jpegFormat?: boolean;
  fiveInchPaper?: boolean;
  renderMode?: RenderMode;
  customBackgroundEnabled?: boolean;
  customBackgroundHex?: string;
  customBackgroundRgb?: [number, number, number] | string | { r: number; g: number; b: number };
  backgroundRgb?: [number, number, number];
  pluginFlags?: string[];
  spec?: Record<string, unknown>;
  aiPro?: AiProRequest;
  [key: string]: unknown;
}

export interface ProcessingTask {
  taskId: string;
  status: TaskStatus;
  uploadId: string;
  templateId: string;
  platform: Platform;
  aiMode: AiMode;
  options: TaskOptions;
  officialResult?: ResultFile;
  aiEnhanceResult?: ResultFile;
  freeResult?: ResultFile;
  proResults?: AiProResult[];
  stages?: Record<string, unknown>;
  aiPro?: AiProRequest;
  layoutResult?: ResultFile;
  watermarkedResult?: ResultFile;
  compressedResult?: ResultFile;
  compressedTargetKb?: number;
  qualityReport?: QualityReport;
  warning?: { code: string; message: string };
  warnings?: { code: string; message: string }[];
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
  options?: TaskOptions;
  aiPro?: AiProRequest;
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
  common?: boolean;
}

export interface StudioConfig {
  consent: { required: boolean; title: string; body: string };
  privacy: { retentionHours: number; deletionCopy: string };
  uploadLimits?: { maxBytes: number; maxPixels: number; allowedMimeTypes: string[]; allowedExtensions: string[] };
  aiDisclaimer: string;
  copy: { productName: string; uploadCta: string };
  features: { officialIdPhoto: boolean; aiEnhancePreview: boolean; aiPro?: boolean; wechatMiniappReady: boolean };
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

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? '/api').replace(/\/$/, '');
const useMockApi = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true';

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const stamp = () => Math.random().toString(36).slice(2, 8);
const expiresAt = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString();

function apiUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (apiBaseUrl === '/api' && normalizedPath === '/api') return '/api';
  if (apiBaseUrl === '/api' && normalizedPath.startsWith('/api/')) return normalizedPath;
  return `${apiBaseUrl}${normalizedPath}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { credentials: 'include', ...init });
  if (!response.ok) {
    let apiMessage = `API ${init?.method ?? 'GET'} ${path} failed: ${response.status}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      const error = body.error ?? (typeof body.detail === 'object' ? body.detail.error : undefined);
      const detailMessage = typeof body.detail === 'string' ? body.detail : typeof body.detail === 'object' ? body.detail.message : undefined;
      if (error?.message) {
        apiMessage = `${error.code ?? response.status}: ${error.message}`;
      } else if (detailMessage) {
        apiMessage = detailMessage;
      }
    } catch {
      // Keep the HTTP fallback message when the error body is not JSON.
    }
    throw new Error(apiMessage);
  }
  return response.json() as Promise<T>;
}

export const templates: IdPhotoTemplate[] = [
  { templateId: 'cn-id-1inch', label: '一寸', size: '25.0 × 35.0 mm · 295 × 413 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '常用报名 / 简历 / 证件归档', height: 413, width: 295, dpi: 300, common: true },
  { templateId: 'cn-id-2inch', label: '二寸', size: '35.0 × 53.0 mm · 413 × 626 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '考试 / 档案 / 纸质冲印', height: 626, width: 413, dpi: 300, common: true },
  { templateId: 'cn-photo-03', label: '小一寸', size: '22.0 × 32.0 mm · 260 × 378 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 378, width: 260, dpi: 300, common: true },
  { templateId: 'cn-photo-04', label: '小二寸', size: '35.0 × 45.0 mm · 413 × 531 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 531, width: 413, dpi: 300, common: true },
  { templateId: 'passport-visa', label: '大一寸', size: '33.0 × 48.0 mm · 390 × 567 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '护照、签证材料预检', height: 567, width: 390, dpi: 300, common: true },
  { templateId: 'cn-photo-06', label: '大二寸', size: '35.0 × 53.0 mm · 413 × 626 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 626, width: 413, dpi: 300, common: true },
  { templateId: 'cn-photo-07', label: '五寸', size: '88.9 × 126.9 mm · 1050 × 1499 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 1499, width: 1050, dpi: 300, common: false },
  { templateId: 'cn-photo-08', label: '教师资格证', size: '25.0 × 35.0 mm · 295 × 413 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 413, width: 295, dpi: 300, common: false },
  { templateId: 'cn-photo-09', label: '国家公务员考试', size: '25.0 × 35.0 mm · 295 × 413 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 413, width: 295, dpi: 300, common: false },
  { templateId: 'cn-photo-10', label: '初级会计考试', size: '25.0 × 35.0 mm · 295 × 413 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 413, width: 295, dpi: 300, common: false },
  { templateId: 'cn-photo-11', label: '英语四六级考试', size: '12.2 × 16.3 mm · 144 × 192 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 192, width: 144, dpi: 300, common: false },
  { templateId: 'cn-photo-12', label: '计算机等级考试', size: '33.0 × 48.0 mm · 390 × 567 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 567, width: 390, dpi: 300, common: false },
  { templateId: 'cn-photo-13', label: '研究生考试', size: '45.0 × 60.0 mm · 531 × 709 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '官方结果由 Hivision IDCreator 渲染。', height: 709, width: 531, dpi: 300, common: false },
  { templateId: 'cn-photo-14', label: '社保卡', size: '30.3 × 37.3 mm · 358 × 441 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '制卡与归档参考', height: 441, width: 358, dpi: 300, common: false },
  { templateId: 'cn-photo-15', label: '电子驾驶证', size: '22.0 × 32.0 mm · 260 × 378 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '电子证照申领参考', height: 378, width: 260, dpi: 300, common: false },
  { templateId: 'cn-photo-16', label: '美国签证', size: '50.8 × 50.8 mm · 600 × 600 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '签证材料预检', height: 600, width: 600, dpi: 300, common: false },
  { templateId: 'cn-photo-17', label: '日本签证', size: '25.0 × 35.0 mm · 295 × 413 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '签证材料预检', height: 413, width: 295, dpi: 300, common: false },
  { templateId: 'cn-photo-18', label: '韩国签证', size: '35.0 × 45.0 mm · 413 × 531 px', headRange: 'IDCreator 裁切参数可调：head/top/dpi 已接入；其余高级项按能力逐步开放。', printNote: '签证材料预检', height: 531, width: 413, dpi: 300, common: false },
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
  aiDisclaimer: 'AI enhance / AI Pro are optional and visually separated from official ID photo output. AI Pro may use provider or fallback depending on server credentials.',
  copy: { productName: 'HivisionIDPhotos Studio', uploadCta: 'Select portrait' },
  features: { officialIdPhoto: true, aiEnhancePreview: true, aiPro: true, wechatMiniappReady: true },
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
  const aiPro = input.aiPro ?? input.options?.aiPro;
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
      aiPro,
    },
    aiPro,
    proResults: [],
    stages: { core: { status: 'queued' }, aiPro: { status: aiPro?.enabled ? 'queued' : 'skipped' } },
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
  const derivedResult = (lane: string): ResultFile => ({
    fileId: `file_result_${lane}_${task.taskId.slice(-6)}`,
    previewUrl: `#mock-${lane}-preview-miniapp-compatible`,
    downloadUrl: `#mock-${lane}-download-miniapp-compatible`,
    expiresAt: expiresAt(90),
  });

  return {
    ...task,
    status: 'succeeded',
    officialResult,
    freeResult: officialResult,
    layoutResult: task.options.printLayoutEnabled ? derivedResult('layout') : undefined,
    watermarkedResult: task.options.watermarkEnabled ? derivedResult('watermarked') : undefined,
    compressedResult: typeof task.options.imageKb === 'number' ? derivedResult('compressed') : undefined,
    compressedTargetKb: typeof task.options.imageKb === 'number' ? task.options.imageKb : undefined,
    aiEnhanceResult: task.options.renderAiEnhancePreview ? derivedResult('ai') : undefined,
    proResults: task.aiPro?.enabled ? task.aiPro.modes.map((mode) => ({
      mode,
      status: 'mock_completed',
      imageUrl: officialResult.previewUrl,
      previewUrl: officialResult.previewUrl,
      usageLabel: mode === 'executive_headshot' ? 'non_official_portrait' : mode === 'ai_blue_formal_id_photo' ? 'official_candidate' : 'preview_repair',
      promptTemplateId: mode === 'executive_headshot' ? 'executive_headshot_apple_style' : mode === 'ai_blue_formal_id_photo' ? 'ai_blue_formal_id_photo' : 'ai_repair_basic',
      templateVersion: '2026-05-phase1',
      paid: false,
      qualityReport: { mock: true, source: 'core_quality_report' },
      downloadUrl: officialResult.downloadUrl,
      promptMetadata: {
        provider: 'mock',
        providerStatus: 'no_credentials',
        model: null,
        inputSource: 'freeResult',
        mock: true,
        fallback: true,
        errorCode: 'NO_CREDENTIALS',
        durationMs: 0,
        finalPromptHash: null,
        mockSource: 'freeResult',
        selectedParams: task.aiPro?.promptParams ?? {},
      },
      mock: true,
    })) : [],
    stages: { core: { status: 'completed' }, aiPro: { status: task.aiPro?.enabled ? 'fallback' : 'skipped' } },
    qualityReport: {
      score: 92,
      passed: true,
      metrics: {
        dimensions: { match: true },
        face: { count: 1, detector: 'mock' },
        backgroundColor: { meanDelta: 2.4 },
      },
      warnings: [],
      errors: [],
      suggestions: ['Mock precheck passed; verify final agency-specific requirements before submission.'],
    },
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
      phase: '5E',
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
