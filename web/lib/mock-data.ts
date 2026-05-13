export type TaskStatus = 'queued' | 'processing' | 'succeeded' | 'failed' | 'expired';

export const stages = [
  { label: 'Upload', detail: 'multipart/form-data image intake', state: 'complete' },
  { label: 'Specification', detail: '1-inch CN ID · white background', state: 'active' },
  { label: 'Task', detail: 'queued → processing → succeeded', state: 'pending' },
  { label: 'Result', detail: 'official output file handles', state: 'pending' },
  { label: 'AI preview', detail: 'optional server-side enhance branch', state: 'pending' },
] as const;

export const mockTask = {
  upload: {
    uploadId: 'upl_demo_precision_001',
    fileId: 'file_demo_portrait_001',
    mimeType: 'image/jpeg',
    expiresAt: '2026-05-14T18:00:00+08:00',
  },
  task: {
    taskId: 'task_demo_certificate_001',
    status: 'processing' as TaskStatus,
    officialResult: {
      fileId: 'file_demo_official_001',
      previewUrl: 'mock://official-preview-compatible-with-wx.previewImage',
      downloadUrl: 'mock://official-download-compatible-with-wx.downloadFile',
      expiresAt: '2026-05-14T18:30:00+08:00',
    },
    aiEnhanceResult: {
      fileId: 'file_demo_ai_preview_001',
      previewUrl: 'mock://ai-preview-separated-from-official-result',
      downloadUrl: 'mock://ai-download-separated-from-official-result',
      expiresAt: '2026-05-14T18:30:00+08:00',
    },
  },
};

export const apiCards = [
  ['GET', '/api/config', 'Consent, privacy, AI disclaimer, copy, features'],
  ['POST', '/api/uploads', 'wx.uploadFile-compatible multipart upload'],
  ['POST', '/api/tasks', 'Create official/AI-separated processing task'],
  ['GET', '/api/tasks/{id}', 'Poll queued/processing/succeeded/failed/expired'],
  ['GET', '/api/templates', 'Shared ID photo specifications'],
  ['GET', '/api/health', 'Service health and version'],
] as const;
