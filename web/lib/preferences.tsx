'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export type LanguagePreference = 'zh-CN' | 'en-US';

type Dictionary = Record<string, string>;
type TranslationKey = keyof typeof dictionaries['zh-CN'];

const THEME_KEY = 'idphoto-ai.theme';
const LANGUAGE_KEY = 'idphoto-ai.language';

const dictionaries = {
  'zh-CN': {
    appSubtitle: 'HivisionIDPhotos',
    studioTitle: '精密证件照工作台',
    studioIntro: '面向证件照合规输出的精密工作台，适配 Web 与后续小程序客户端。',
    phaseBadge: 'Phase 5E',
    settings: '设置',
    logout: '退出',
    settingsTitle: '实验室控制台设置',
    settingsIntro: '调整外观、语言与 AI Provider 预留项。偏好只保存在本机浏览器。',
    closeSettings: '关闭设置',
    appearance: '外观',
    appearanceHint: '主题会立即影响背景、卡片、文字与边框。',
    themeLight: '浅色',
    themeDark: '深色',
    themeSystem: '跟随系统',
    language: '语言',
    languageHint: '默认优先中文，可切换英文；选择会保存到 localStorage。',
    aiProvider: 'AI Provider（预留）',
    aiProviderHint: '当前为 local-derived-preview。未来可接 GPT-image-2，但此版本不启用真实调用。',
    currentProvider: '当前 Provider',
    futureProvider: 'GPT-image-2',
    reservedReadonly: '即将支持 / 未配置 / 只读预留',
    providerBoundary: '正式证件照仍由 IDCreator 生成；AI Provider 只影响增强预览，不替代 officialResult。',
    providerNotConnected: 'GPT-image-2 未接入',
    uploadStage: '上传',
    uploadStageDetail: '本地文件接入 · multipart 合约',
    specStage: '规格',
    specStageDetail: '一寸 · 二寸 · 护照/签证',
    taskStage: '任务',
    taskStageDetail: '排队 → 处理中 → 成功',
    resultStage: '结果',
    resultStageDetail: '官方输出文件句柄',
    aiPreviewStage: 'AI 预览',
    aiPreviewStageDetail: '可选但当前禁用的增强分支',
    privacyNote: '隐私说明：仅接受 JPG/PNG/WebP，限制大小，并随生成结果自动过期。',
    adminStats: '管理统计',
    refresh: '刷新',
    phase: '阶段',
    logins24h: '24h 登录',
    uploads24h: '24h 上传',
    tasksOkFail: '任务成功/失败',
    downloads: '下载',
    rateHits: '限流命中',
    uploadsDisk: '上传占用',
    resultsDisk: '结果占用',
    statsLoading: '登录后加载统计。API: /api/admin/stats',
    apiConfigPurpose: '同意、隐私、AI 免责声明、文案、功能开关',
    apiUploadsPurpose: '兼容 wx.uploadFile 的 multipart 上传',
    apiTasksPurpose: '创建官方/AI 分离处理任务',
    apiTaskPollPurpose: '轮询 queued/processing/succeeded/failed/expired',
    apiTemplatesPurpose: '共享证件照规格',
    apiHealthPurpose: '服务健康与版本',
    apiAdminStatsPurpose: '已认证的可观测性摘要',
    loginTitle: '工作台登录',
    loginIntro: '登录后可上传照片、处理任务并获取签名下载链接。',
    username: '用户名',
    password: '密码',
    signingIn: '登录中…',
    signIn: '登录',
    checkingSession: '检查登录状态…',
    loginFailed: '登录失败。',
    uploadFailed: '上传失败。',
    taskFailed: '任务创建失败。',
    uploadBay: '上传舱',
    uploadAligned: 'wx.uploadFile 对齐',
    dropSelectPortrait: '拖放或选择人像照片',
    uploadHelp: '浏览器端预览。结构对齐 Web、移动 Web 与后续小程序的 multipart/form-data 上传句柄，不依赖纯 cookie 假设。',
    portraitIntake: '人像接入',
    creatingUpload: '创建上传句柄…',
    selectPortrait: '选择照片',
    uploadTypes: 'JPG / PNG / WebP · Phase 2 本地处理',
    specRuler: '规格标尺',
    selectSpec: '选择证件照规格',
    backgroundCassette: '底色匣',
    selectBackground: '选择底色',
    optionalBranch: '可选分支',
    aiEnhancePreview: 'AI 增强预览',
    aiComingSoon: '即将支持：与正式结果分离，仅服务端执行。',
    disabled: '禁用',
    advancingTask: '任务推进中…',
    createTask: '创建证件照任务',
    bgWhite: '白底',
    bgBlue: '蓝底',
    bgRed: '红底',
    bgGray: '灰底',
    bgWhiteNote: '通用证件',
    bgBlueNote: '考试 / 档案',
    bgRedNote: '政务材料',
    bgGrayNote: '签证预览',
    taskModel: '任务模型',
    idle: '空闲',
    queued: '已排队',
    processing: '处理中',
    succeeded: '已成功',
    failed: '失败',
    expired: '已过期',
    queuedDetail: '任务已接收；通过轮询推进，避免阻塞请求。',
    processingDetail: '官方裁切、换底与合规渲染通过 IDCreator API adapter 执行。',
    succeededDetail: '结果句柄包含 fileId、previewUrl、downloadUrl、expiresAt。',
    failedDetail: '合约保留可重试错误结构，供服务端校验失败时使用。',
    expiredDetail: '过期句柄保持 Web 与小程序行为一致。',
    platformFallback: 'web / 小程序就绪',
    officialResult: '官方结果',
    outputCard: '证件照输出卡',
    ready: '就绪',
    waiting: '等待中',
    resultIntro: 'Phase 5B 从确定性的 Hivision IDCreator 返回短期签名 officialResult URL。AI 预览通道标记为 local-derived-preview，永不替代 officialResult。',
    spec: '规格',
    background: '底色',
    resultSource: '结果来源',
    aiPreview: 'AI 预览',
    signedPreview: '签名预览',
    signedDownload: '签名下载',
    aiLane: 'AI 增强通道',
    aiLaneCopy: '可选预览保持在独立 AI 通道。当前状态为 {kind}，不会替代官方结果卡，也不会在客户端暴露 provider key/base URL。',
    openLocalPreview: '打开 local-derived-preview',
    previewAlt: '已选择人像预览',
    workbenchAlt: '工作台人像预览',
    officialAlt: 'IDCreator 官方结果预览',
    sourceAlt: '源人像预览',
  },
  'en-US': {
    appSubtitle: 'HivisionIDPhotos',
    studioTitle: 'Precision Studio',
    studioIntro: 'A measured, compliance-first workbench for certificate-ready portraits across web and future miniapp clients.',
    phaseBadge: 'Phase 5E',
    settings: 'Settings',
    logout: 'Logout',
    settingsTitle: 'Laboratory Console Settings',
    settingsIntro: 'Adjust appearance, language, and the reserved AI Provider lane. Preferences stay in this browser.',
    closeSettings: 'Close settings',
    appearance: 'Appearance',
    appearanceHint: 'Theme changes immediately affect backgrounds, cards, text, and borders.',
    themeLight: 'Light',
    themeDark: 'Dark',
    themeSystem: 'System',
    language: 'Language',
    languageHint: 'Chinese is preferred by default; English remains available. The choice is saved in localStorage.',
    aiProvider: 'AI Provider (reserved)',
    aiProviderHint: 'Current provider is local-derived-preview. GPT-image-2 may be added later, but no real call is enabled here.',
    currentProvider: 'Current Provider',
    futureProvider: 'GPT-image-2',
    reservedReadonly: 'Coming soon / unconfigured / read-only reservation',
    providerBoundary: 'Official ID photos are still generated by IDCreator; AI Provider only affects enhanced previews and never replaces officialResult.',
    providerNotConnected: 'GPT-image-2 is not connected',
    uploadStage: 'Upload',
    uploadStageDetail: 'local File intake · multipart contract',
    specStage: 'Specification',
    specStageDetail: '1-inch · 2-inch · passport/visa',
    taskStage: 'Task',
    taskStageDetail: 'queued → processing → succeeded',
    resultStage: 'Result',
    resultStageDetail: 'official output file handles',
    aiPreviewStage: 'AI preview',
    aiPreviewStageDetail: 'optional disabled enhance branch',
    privacyNote: 'Privacy note: uploads accept JPG/PNG/WebP only, are size-limited, and expire automatically with generated results.',
    adminStats: 'Admin stats',
    refresh: 'Refresh',
    phase: 'Phase',
    logins24h: '24h logins',
    uploads24h: '24h uploads',
    tasksOkFail: 'Tasks ok/fail',
    downloads: 'Downloads',
    rateHits: 'Rate hits',
    uploadsDisk: 'Uploads disk',
    resultsDisk: 'Results disk',
    statsLoading: 'Stats load after login. API: /api/admin/stats',
    apiConfigPurpose: 'Consent, privacy, AI disclaimer, copy, features',
    apiUploadsPurpose: 'wx.uploadFile-compatible multipart upload',
    apiTasksPurpose: 'Create official/AI-separated processing task',
    apiTaskPollPurpose: 'Poll queued/processing/succeeded/failed/expired',
    apiTemplatesPurpose: 'Shared ID photo specifications',
    apiHealthPurpose: 'Service health and version',
    apiAdminStatsPurpose: 'Authenticated observability summary',
    loginTitle: 'Studio Login',
    loginIntro: 'Sign in to access uploads, task processing, and signed downloads.',
    username: 'Username',
    password: 'Password',
    signingIn: 'Signing in…',
    signIn: 'Sign in',
    checkingSession: 'Checking session…',
    loginFailed: 'Login failed.',
    uploadFailed: 'Upload failed.',
    taskFailed: 'Task creation failed.',
    uploadBay: 'Upload bay',
    uploadAligned: 'wx.uploadFile aligned',
    dropSelectPortrait: 'Drop or select a portrait',
    uploadHelp: 'Browser-only preview. The shape mirrors multipart/form-data upload handles for web, mobile web, and future miniapp clients—no cookie-only assumption.',
    portraitIntake: 'Portrait intake',
    creatingUpload: 'Creating upload handle…',
    selectPortrait: 'Select portrait',
    uploadTypes: 'JPG / PNG / WebP · handled locally in Phase 2',
    specRuler: 'Specification ruler',
    selectSpec: 'Select ID photo specification',
    backgroundCassette: 'Background cassette',
    selectBackground: 'Select background',
    optionalBranch: 'Optional branch',
    aiEnhancePreview: 'AI Enhance preview',
    aiComingSoon: 'Coming soon: separated from official result and server-side only.',
    disabled: 'Disabled',
    advancingTask: 'Advancing task…',
    createTask: 'Create ID photo task',
    bgWhite: 'White',
    bgBlue: 'Blue',
    bgRed: 'Red',
    bgGray: 'Gray',
    bgWhiteNote: 'General documents',
    bgBlueNote: 'Exams / records',
    bgRedNote: 'Government material',
    bgGrayNote: 'Visa preview',
    taskModel: 'Task model',
    idle: 'idle',
    queued: 'Queued',
    processing: 'Processing',
    succeeded: 'Succeeded',
    failed: 'Failed',
    expired: 'Expired',
    queuedDetail: 'Task accepted; safe to poll rather than blocking request.',
    processingDetail: 'Official crop, background, and compliance render run through the IDCreator API adapter.',
    succeededDetail: 'Result handles include fileId, previewUrl, downloadUrl, expiresAt.',
    failedDetail: 'Contract reserves retryable error shape for server validation failures.',
    expiredDetail: 'Expiring handles keep web and miniapp behavior aligned.',
    platformFallback: 'web / miniapp-ready',
    officialResult: 'Official result',
    outputCard: 'Certificate output card',
    ready: 'ready',
    waiting: 'waiting',
    resultIntro: 'Phase 5B returns short-lived signed officialResult URLs from deterministic Hivision IDCreator. The AI preview lane is labelled local-derived-preview and never replaces officialResult.',
    spec: 'Spec',
    background: 'Background',
    resultSource: 'Result source',
    aiPreview: 'AI preview',
    signedPreview: 'Signed preview',
    signedDownload: 'Signed download',
    aiLane: 'AI Enhance lane',
    aiLaneCopy: 'Optional preview stays in a separate AI lane. It is currently {kind} and will never replace this official result card or expose provider keys/base URLs in the client.',
    openLocalPreview: 'Open local-derived-preview',
    previewAlt: 'Selected portrait preview',
    workbenchAlt: 'Workbench portrait preview',
    officialAlt: 'Official IDCreator result preview',
    sourceAlt: 'Source portrait preview',
  },
} as const;

type PreferencesContextValue = {
  theme: ThemePreference;
  language: LanguagePreference;
  setTheme: (theme: ThemePreference) => void;
  setLanguage: (language: LanguagePreference) => void;
  t: (key: TranslationKey, replacements?: Record<string, string>) => string;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function getStoredTheme(): ThemePreference {
  if (typeof window === 'undefined') return 'system';
  const value = window.localStorage.getItem(THEME_KEY);
  return value === 'light' || value === 'dark' || value === 'system' ? value : 'system';
}

function getStoredLanguage(): LanguagePreference {
  if (typeof window === 'undefined') return 'zh-CN';
  const value = window.localStorage.getItem(LANGUAGE_KEY);
  return value === 'en-US' || value === 'zh-CN' ? value : 'zh-CN';
}

function applyTheme(theme: ThemePreference) {
  const root = document.documentElement;
  const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const resolved = theme === 'system' ? (darkQuery.matches ? 'dark' : 'light') : theme;
  root.dataset.theme = resolved;
  root.dataset.themePreference = theme;
  root.style.colorScheme = resolved;
}

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>('system');
  const [language, setLanguageState] = useState<LanguagePreference>('zh-CN');

  useEffect(() => {
    setThemeState(getStoredTheme());
    setLanguageState(getStoredLanguage());
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    applyTheme(theme);
    const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => applyTheme(theme);
    darkQuery.addEventListener('change', onChange);
    return () => darkQuery.removeEventListener('change', onChange);
  }, [theme]);

  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<PreferencesContextValue>(() => {
    const dictionary = dictionaries[language] as Dictionary;
    return {
      theme,
      language,
      setTheme(nextTheme) {
        window.localStorage.setItem(THEME_KEY, nextTheme);
        setThemeState(nextTheme);
      },
      setLanguage(nextLanguage) {
        window.localStorage.setItem(LANGUAGE_KEY, nextLanguage);
        setLanguageState(nextLanguage);
      },
      t(key, replacements) {
        let text = dictionary[key] ?? dictionaries['zh-CN'][key] ?? String(key);
        if (replacements) {
          Object.entries(replacements).forEach(([name, value]) => {
            text = text.replace(`{${name}}`, value);
          });
        }
        return text;
      },
    };
  }, [language, theme]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error('usePreferences must be used inside PreferencesProvider');
  return context;
}
