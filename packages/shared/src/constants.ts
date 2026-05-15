export const TASK_STATUSES = [
  'queued',
  'processing',
  'succeeded',
  'failed',
  'expired',
] as const;

export const AI_MODES = ['none', 'preview', 'enhance'] as const;

export const PLATFORMS = ['web', 'mobileWeb', 'wechatMiniapp'] as const;

export const API_ENDPOINTS = {
  config: '/api/config',
  uploads: '/api/uploads',
  tasks: '/api/tasks',
  templates: '/api/templates',
  health: '/api/health',
} as const;
