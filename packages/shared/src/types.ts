import type { AI_MODES, PLATFORMS, TASK_STATUSES } from './constants';

export type TaskStatus = (typeof TASK_STATUSES)[number];
export type AiMode = (typeof AI_MODES)[number];
export type Platform = (typeof PLATFORMS)[number];

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
