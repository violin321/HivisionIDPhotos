// Mock Web v2 client aligned with api/contract.md.
// Designed so the same upload/task/result flow can later back web and WeChat Mini Program clients.
// TODO: move these narrow contract types to packages/shared workspace exports when Next workspace imports are formalized.

export type TaskStatus = 'queued' | 'processing' | 'succeeded' | 'failed' | 'expired';
export type Platform = 'web' | 'mobileWeb' | 'wechatMiniapp';
export type AiMode = 'none' | 'preview' | 'enhance';
export type BackgroundColor = 'white' | 'blue' | 'red' | 'gray';

export interface UploadHandle {
  uploadId: string;
  fileId: string;
  mimeType: string;
  expiresAt: string;
}

export interface ResultFile {
  fileId: string;
  previewUrl: string;
  downloadUrl: string;
  expiresAt: string;
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
}

export interface StudioConfig {
  consent: { required: boolean; title: string; body: string };
  privacy: { retentionHours: number; deletionCopy: string };
  aiDisclaimer: string;
  copy: { productName: string; uploadCta: string };
  features: { officialIdPhoto: boolean; aiEnhancePreview: boolean; wechatMiniappReady: boolean };
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const stamp = () => Math.random().toString(36).slice(2, 8);
const expiresAt = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString();

export const templates: IdPhotoTemplate[] = [
  { templateId: 'cn-id-1inch', label: '一寸', size: '25 × 35 mm', headRange: '头顶 3–5 mm · 肩线居中', printNote: '常用报名 / 简历 / 证件归档' },
  { templateId: 'cn-id-2inch', label: '二寸', size: '35 × 49 mm', headRange: '脸部 28–33 mm · 留白均衡', printNote: '考试 / 档案 / 纸质冲印' },
  { templateId: 'passport-visa', label: '护照 / 签证', size: '33 × 48 mm', headRange: '眼线参考 · ICAO 风格构图', printNote: '护照、签证材料预检' },
];

export const config: StudioConfig = {
  consent: {
    required: true,
    title: 'Photo processing consent',
    body: 'Your portrait stays inside this browser mock during Phase 2; production uploads create expiring file handles.',
  },
  privacy: {
    retentionHours: 24,
    deletionCopy: 'Uploads and generated files expire automatically.',
  },
  aiDisclaimer: 'AI enhance is optional and visually separated from official ID photo output.',
  copy: { productName: 'HivisionIDPhotos Studio', uploadCta: 'Select portrait' },
  features: { officialIdPhoto: true, aiEnhancePreview: true, wechatMiniappReady: true },
};

export async function createUpload(file: File): Promise<UploadHandle> {
  await wait(260);
  return {
    uploadId: `upl_mock_${stamp()}`,
    fileId: `file_source_${stamp()}`,
    mimeType: file.type || 'image/jpeg',
    expiresAt: expiresAt(60),
  };
}

export async function createTask(input: TaskCreateInput): Promise<ProcessingTask> {
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
    },
  };
}

export async function getTask(task: ProcessingTask, tick: number): Promise<ProcessingTask> {
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

export async function getConfig() {
  await wait(80);
  return config;
}

export async function getTemplates() {
  await wait(80);
  return templates;
}
