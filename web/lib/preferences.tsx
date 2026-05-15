'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type ThemeModePreference = 'light' | 'dark' | 'system';
export type ThemePresetPreference = 'precision' | 'warm-paper' | 'darkroom';
export type LanguagePreference = 'zh-CN' | 'en-US';

type Dictionary = Record<string, string>;
type TranslationKey = keyof typeof dictionaries['zh-CN'];

const THEME_MODE_KEY = 'idphoto-ai.themeMode';
const LEGACY_THEME_KEY = 'idphoto-ai.theme';
const THEME_PRESET_KEY = 'idphoto-ai.themePreset';
const LANGUAGE_KEY = 'idphoto-ai.language';

const dictionaries = {
  'zh-CN': {
    appSubtitle: 'HivisionIDPhotos',
    studioTitle: '精密证件照工作台',
    studioIntro: '上传人像、选择规格与底色，生成可下载的标准证件照。高级参数已折叠，日常流程保持干净。',
    phaseBadge: '工作台',
    settings: '设置',
    logout: '退出',
    settingsTitle: '工作台设置',
    settingsIntro: '调整外观与语言偏好。设置仅保存在当前浏览器。',
    closeSettings: '关闭设置',
    appearance: '明暗模式',
    appearanceHint: '选择 light / dark / system；明暗模式与主题风格可独立扩展。',
    themeLight: '浅色',
    themeDark: '深色',
    themeSystem: '跟随系统',
    themePreset: '主题风格',
    themePresetHint: '主题通过 CSS token 落地，后续可继续增加预设。',
    themePrecision: 'Precision 精密蓝图',
    themeWarmPaper: 'Warm Paper 暖纸档案',
    themeDarkroom: 'Darkroom 暗房',
    language: '语言',
    languageHint: '默认优先中文，可切换英文；选择会保存到 localStorage。',
    workspacePreferences: '工作台偏好',
    workspacePreferencesHint: '普通用户默认只看到生成证件照所需功能；维护信息集中在单独层级。',
    providerBoundary: '正式证件照始终由 IDCreator 生成；增强预览不会替代官方结果。',
    uploadStage: '上传',
    uploadStageDetail: '选择清晰正面人像',
    specStage: '规格',
    specStageDetail: '常用尺寸，也可搜索完整规格',
    taskStage: '任务',
    taskStageDetail: '提交后显示当前进度',
    resultStage: '结果',
    resultStageDetail: '预览并下载正式结果',
    aiPreviewStage: 'AI 预览',
    aiPreviewStageDetail: '增强预览默认关闭',
    privacyNote: '隐私说明：仅接受 JPG/PNG/WebP，文件有大小限制，并随生成结果自动过期。',
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
    statsLoading: '登录后加载统计。',
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
    uploadAligned: '当前照片',
    dropSelectPortrait: '拖放或选择人像照片',
    uploadHelp: '上传一张清晰正面人像。上传成功后这里保留素材摘要，照片预览集中显示在右侧当前照片卡。',
    portraitIntake: '人像接入',
    creatingUpload: '创建上传句柄…',
    selectPortrait: '选择照片',
    uploadTypes: '支持 JPG / PNG / WebP',
    specRuler: '规格标尺',
    selectSpec: '选择证件照规格',
    templateReadyBadge: '规格已就绪',
    backgroundCassette: '底色匣',
    selectBackground: '选择底色',
    optionalBranch: '可选分支',
    aiEnhancePreview: 'AI 增强预览',
    aiComingSoon: '增强预览仍为独立通道，当前默认关闭。',
    disabled: '禁用',
    advancingTask: '任务推进中…',
    createTask: '创建证件照任务',
    commonSpecsOnly: '常用规格',
    moreSpecs: '更多规格',
    allSpecs: '全部规格',
    changeSpec: '更换规格',
    currentSpec: '当前选中规格',
    specCatalog: '规格目录',
    specDialogHint: '完整规格放在独立选择器里滚动浏览，主流程只保留当前规格摘要。',
    specSummaryHint: '需要美国签证、韩国签证、考试等更多规格时，点击更换规格进入完整目录。',
    closeSpecSelector: '关闭',
    selectedSpec: '已选择',
    selectThisSpec: '选择此规格',
    noSpecsFound: '未找到匹配规格。',
    specCategoryAll: '全部',
    specCategoryCommon: '常用',
    specCategoryExam: '考试',
    specCategoryVisa: '签证',
    specCategoryCredential: '证件',
    searchSpecs: '搜索尺寸、用途或说明',
    commonSpecsHint: '主流程默认只展示最常用规格，避免把普通用户界面塞满。',
    moreSpecsHint: '已展开完整规格列表，可按名称或用途搜索。',
    moreSpecsBadge: '更多',
    advancedParams: '高级参数',
    advancedParamsTitle: 'Hivision 核心创作参数',
    advancedParamsHint: 'head/top/dpi、美颜强度、目标 KB、水印与打印排版均已接入后端任务；高级项默认折叠。',
    headMeasureRatio: '面部比例 head_measure_ratio',
    topDistance: '头顶留白 top_distance',
    outputDpi: '输出 DPI',
    whiteningStrengthLabel: '美白 whitening',
    brightnessStrengthLabel: '亮度 brightness',
    contrastStrengthLabel: '对比度 contrast',
    saturationStrengthLabel: '饱和度 saturation',
    sharpenStrengthLabel: '锐化 sharpen',
    imageKbLabel: '目标 KB（压缩副本）',
    imageKbPendingHint: '当前 Web task 仅记录该参数，任务主链路尚未接入按 KB 重编码。',
    imageKbReadyHint: 'exact 会补齐到目标 KB；max 只保证不超过目标，避免尾部 padding。',
    imageKbModeLabel: 'KB 策略',
    imageKbModeExact: '精确 KB',
    imageKbModeMax: '不超过 KB',
    watermarkLabel: '水印',
    watermarkColor: '水印颜色',
    watermarkSize: '字号',
    watermarkOpacity: '透明度',
    watermarkAngle: '角度',
    watermarkSpace: '间距',
    printLayoutLabel: '打印排版',
    layoutPaperSizeLabel: '排版纸张',
    layoutPaperSizeHint: '默认六寸，可切换五寸或 A4；仅影响独立打印排版照。',
    layoutCropLineLabel: '排版裁剪线',
    renderModeLabel: '背景渲染模式',
    renderModeSolid: '纯色',
    renderModeUpDown: '上下渐变到白色',
    renderModeCenter: '中心渐变到白色',
    horizontalFlipLabel: '水平翻转',
    faceAlignLabel: '人脸旋转对齐',
    jpegFormatLabel: '官方结果 JPEG',
    customBackgroundLabel: '自定义背景色',
    customBackgroundHex: '自定义 HEX / 颜色',
    customBackgroundRgb: 'RGB 通道',
    pendingFeaturesHint: '未接入项会明确标注，不假装已经生效。若后端链路补齐，可直接复用这些字段。',
    connectedFeaturesHint: '原项目插件、渲染模式与自定义底色已接入；衍生插件失败只记录 warning，不影响官方证件照。',
    bgWhite: '白底',
    bgBlue: '蓝底',
    bgRed: '红底',
    bgGray: '灰底',
    bgWhiteNote: '通用证件',
    bgBlueNote: '考试 / 档案',
    bgRedNote: '政务材料',
    bgGrayNote: '签证预览',
    taskModel: '生成进度',
    idle: '空闲',
    queued: '已排队',
    processing: '处理中',
    succeeded: '已成功',
    failed: '失败',
    expired: '已过期',
    queuedDetail: '任务已接收；通过轮询推进，避免阻塞请求。',
    processingDetail: '裁切、换底与合规渲染在服务端完成。',
    succeededDetail: '结果会返回预览、下载与过期时间。',
    failedDetail: '合约保留可重试错误结构，供服务端校验失败时使用。',
    expiredDetail: '过期后请重新生成，避免继续使用失效链接。',
    platformFallback: 'Web 工作台',
    officialResult: '生成结果',
    outputCard: '证件照输出卡',
    ready: '就绪',
    waiting: '等待中',
    resultIntro: '处理完成后，这里只展示最终标准证件照，不再重复展示源照片。',
    spec: '规格',
    background: '底色',
    resultSource: '结果来源',
    aiPreview: 'AI 预览',
    signedPreview: '签名预览',
    signedDownload: '签名下载',
    qualityReportTitle: '合规预检',
    qualityPassed: '通过自动预检',
    qualityNeedsReview: '需人工复核 / 调整',
    pluginWarnings: '插件结果提醒',
    layoutResult: '打印排版照',
    layoutResultCopy: '按原项目 layout_calculator 生成独立打印排版照。',
    compressedResult: '目标 KB 副本',
    compressedResultCopy: '按 {kb} KB 生成 JPEG 压缩副本，官方原图不变。',
    watermarkedResult: '水印照',
    watermarkedResultCopy: '使用原项目水印插件生成独立水印版本。',
    aiLane: 'AI 增强通道',
    aiLaneCopy: '增强预览与正式证件照结果分开显示，当前状态为 {kind}。',
    openLocalPreview: '打开增强预览',
    previewAlt: '已选择人像预览',
    workbenchAlt: '工作台人像预览',
    officialAlt: 'IDCreator 官方结果预览',
    sourceAlt: '源人像预览',
    workbenchTab: '普通工作台',
    maintenanceTab: '维护/管理',
    maintenanceTitle: '维护与管理层',
    maintenanceIntro: '这里集中显示调试 ID、任务细节、API 阶段与运行统计；普通工作台默认隐藏这些内部信息。',
    materialSummary: '素材摘要',
    materialReady: '已上传，可创建任务',
    noMaterial: '尚未选择照片',
    currentPhoto: '当前照片',
    internalDiagnostics: '内部诊断',
    publicProgressHint: '生成进度只展示状态；内部 ID 请到维护/管理层查看。',
  },
  'en-US': {
    appSubtitle: 'HivisionIDPhotos',
    studioTitle: 'Precision Studio',
    studioIntro: 'Upload a portrait, choose spec and background, then generate a downloadable standard ID photo. Advanced controls stay folded away from the daily path.',
    phaseBadge: 'Workbench',
    settings: 'Settings',
    logout: 'Logout',
    settingsTitle: 'Workbench Settings',
    settingsIntro: 'Adjust appearance and language preferences. Settings stay in this browser.',
    closeSettings: 'Close settings',
    appearance: 'Theme mode',
    appearanceHint: 'Choose light / dark / system; mode and visual preset are separate for future expansion.',
    themeLight: 'Light',
    themeDark: 'Dark',
    themeSystem: 'System',
    themePreset: 'Theme preset',
    themePresetHint: 'Presets are backed by CSS tokens so more themes can be added later.',
    themePrecision: 'Precision blueprint',
    themeWarmPaper: 'Warm Paper archive',
    themeDarkroom: 'Darkroom',
    language: 'Language',
    languageHint: 'Chinese is preferred by default; English remains available. The choice is saved in localStorage.',
    workspacePreferences: 'Studio preferences',
    workspacePreferencesHint: 'The default workbench shows only ID-photo creation; maintenance details live in a separate layer.',
    providerBoundary: 'Official ID photos are still generated by IDCreator; enhanced previews never replace the official result.',
    uploadStage: 'Upload',
    uploadStageDetail: 'Choose a clear front-facing portrait',
    specStage: 'Specification',
    specStageDetail: 'Common presets plus searchable full catalog',
    taskStage: 'Task',
    taskStageDetail: 'Show only current user-facing progress',
    resultStage: 'Result',
    resultStageDetail: 'Preview and download the final result',
    aiPreviewStage: 'AI preview',
    aiPreviewStageDetail: 'Enhance preview stays off by default',
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
    statsLoading: 'Stats load after login.',
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
    uploadAligned: 'Current photo',
    dropSelectPortrait: 'Drop or select a portrait',
    uploadHelp: 'Upload a clear front-facing portrait. After upload, this area keeps the material summary while the large preview stays in the Current photo card.',
    portraitIntake: 'Portrait intake',
    creatingUpload: 'Creating upload handle…',
    selectPortrait: 'Select portrait',
    uploadTypes: 'Supports JPG / PNG / WebP',
    specRuler: 'Specification ruler',
    selectSpec: 'Select ID photo specification',
    templateReadyBadge: 'Templates ready',
    backgroundCassette: 'Background cassette',
    selectBackground: 'Select background',
    optionalBranch: 'Optional branch',
    aiEnhancePreview: 'AI Enhance preview',
    aiComingSoon: 'Enhanced preview remains a separate lane and is off by default.',
    disabled: 'Disabled',
    advancingTask: 'Advancing task…',
    createTask: 'Create ID photo task',
    commonSpecsOnly: 'Common specs',
    moreSpecs: 'More specs',
    allSpecs: 'All specs',
    changeSpec: 'Change spec',
    currentSpec: 'Current specification',
    specCatalog: 'Spec catalog',
    specDialogHint: 'The full catalog scrolls inside this picker while the main flow keeps only the current spec summary.',
    specSummaryHint: 'Need US visa, Korea visa, exam, or other presets? Open the catalog with Change spec.',
    closeSpecSelector: 'Close',
    selectedSpec: 'Selected',
    selectThisSpec: 'Select this spec',
    noSpecsFound: 'No matching specifications found.',
    specCategoryAll: 'All',
    specCategoryCommon: 'Common',
    specCategoryExam: 'Exam',
    specCategoryVisa: 'Visa',
    specCategoryCredential: 'Credential',
    searchSpecs: 'Search size, use case, or note',
    commonSpecsHint: 'The main flow keeps only the most common presets visible by default.',
    moreSpecsHint: 'Full preset catalog is open; search by name or scenario.',
    moreSpecsBadge: 'More',
    advancedParams: 'Advanced parameters',
    advancedParamsTitle: 'Core Hivision controls',
    advancedParamsHint: 'head/top/dpi, beauty strengths, target KB, watermark, and print layout are live in backend tasks; advanced items stay folded by default.',
    headMeasureRatio: 'Head ratio head_measure_ratio',
    topDistance: 'Top distance top_distance',
    outputDpi: 'Output DPI',
    whiteningStrengthLabel: 'Whitening',
    brightnessStrengthLabel: 'Brightness',
    contrastStrengthLabel: 'Contrast',
    saturationStrengthLabel: 'Saturation',
    sharpenStrengthLabel: 'Sharpen',
    imageKbLabel: 'Target KB (compressed copy)',
    imageKbPendingHint: 'Web task payload keeps this field, but the main task pipeline does not re-encode to a target KB yet.',
    imageKbReadyHint: 'exact pads to the target KB; max stays under the target without tail padding.',
    imageKbModeLabel: 'KB strategy',
    imageKbModeExact: 'Exact KB',
    imageKbModeMax: 'Max KB',
    watermarkLabel: 'Watermark',
    watermarkColor: 'Watermark color',
    watermarkSize: 'Size',
    watermarkOpacity: 'Opacity',
    watermarkAngle: 'Angle',
    watermarkSpace: 'Space',
    printLayoutLabel: 'Print layout',
    layoutPaperSizeLabel: 'Paper size',
    layoutPaperSizeHint: 'Six-inch by default; five-inch and A4 generate independent print sheets.',
    layoutCropLineLabel: 'Layout crop lines',
    renderModeLabel: 'Background render mode',
    renderModeSolid: 'Solid color',
    renderModeUpDown: 'Up/down gradient to white',
    renderModeCenter: 'Center gradient to white',
    horizontalFlipLabel: 'Horizontal flip',
    faceAlignLabel: 'Face rotation align',
    jpegFormatLabel: 'Official result as JPEG',
    customBackgroundLabel: 'Custom background color',
    customBackgroundHex: 'Custom HEX / color',
    customBackgroundRgb: 'RGB channel',
    pendingFeaturesHint: 'Unwired fields stay clearly marked instead of pretending they already work.',
    connectedFeaturesHint: 'Original plugins, render modes, and custom background color are wired; derivative failures become warnings and do not block the official result.',
    bgWhite: 'White',
    bgBlue: 'Blue',
    bgRed: 'Red',
    bgGray: 'Gray',
    bgWhiteNote: 'General documents',
    bgBlueNote: 'Exams / records',
    bgRedNote: 'Government material',
    bgGrayNote: 'Visa preview',
    taskModel: 'Generation progress',
    idle: 'idle',
    queued: 'Queued',
    processing: 'Processing',
    succeeded: 'Succeeded',
    failed: 'Failed',
    expired: 'Expired',
    queuedDetail: 'Task accepted; safe to poll rather than blocking request.',
    processingDetail: 'Cropping, background replacement, and compliance rendering happen server-side.',
    succeededDetail: 'Results return preview, download, and expiry details.',
    failedDetail: 'Contract reserves retryable error shape for server validation failures.',
    expiredDetail: 'Once expired, generate a new result before downloading again.',
    platformFallback: 'Web workbench',
    officialResult: 'Generated result',
    outputCard: 'Certificate output card',
    ready: 'ready',
    waiting: 'waiting',
    resultIntro: 'When processing finishes, only the final standard ID photo appears here; the source portrait is not duplicated.',
    spec: 'Spec',
    background: 'Background',
    resultSource: 'Result source',
    aiPreview: 'AI preview',
    signedPreview: 'Signed preview',
    signedDownload: 'Signed download',
    qualityReportTitle: 'Compliance precheck',
    qualityPassed: 'Passed automatic precheck',
    qualityNeedsReview: 'Needs review / adjustment',
    pluginWarnings: 'Plugin result warnings',
    layoutResult: 'Print layout photo',
    layoutResultCopy: 'Generated as an independent print sheet via the original layout_calculator logic.',
    compressedResult: 'Target KB copy',
    compressedResultCopy: 'JPEG compressed copy targeting {kb} KB; the official original is preserved.',
    watermarkedResult: 'Watermarked photo',
    watermarkedResultCopy: 'Independent watermarked version from the original watermark plugin.',
    aiLane: 'AI Enhance lane',
    aiLaneCopy: 'Enhanced previews stay separate from the official result. Current state: {kind}.',
    openLocalPreview: 'Open enhanced preview',
    previewAlt: 'Selected portrait preview',
    workbenchAlt: 'Workbench portrait preview',
    officialAlt: 'Official IDCreator result preview',
    sourceAlt: 'Source portrait preview',
    workbenchTab: 'User workbench',
    maintenanceTab: 'Maintenance',
    maintenanceTitle: 'Maintenance and admin layer',
    maintenanceIntro: 'Debug IDs, task details, API phase, and runtime stats are grouped here and hidden from the default workbench.',
    materialSummary: 'Material summary',
    materialReady: 'Uploaded, ready to create task',
    noMaterial: 'No portrait selected yet',
    currentPhoto: 'Current photo',
    internalDiagnostics: 'Internal diagnostics',
    publicProgressHint: 'Progress only shows status here. Use Maintenance for internal IDs.',
  },
} as const;

type PreferencesContextValue = {
  themeMode: ThemeModePreference;
  themePreset: ThemePresetPreference;
  language: LanguagePreference;
  setThemeMode: (themeMode: ThemeModePreference) => void;
  setThemePreset: (themePreset: ThemePresetPreference) => void;
  setLanguage: (language: LanguagePreference) => void;
  t: (key: TranslationKey, replacements?: Record<string, string>) => string;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function getStoredThemeMode(): ThemeModePreference {
  if (typeof window === 'undefined') return 'system';
  const value = window.localStorage.getItem(THEME_MODE_KEY) ?? window.localStorage.getItem(LEGACY_THEME_KEY);
  return value === 'light' || value === 'dark' || value === 'system' ? value : 'system';
}

function getStoredThemePreset(): ThemePresetPreference {
  if (typeof window === 'undefined') return 'precision';
  const value = window.localStorage.getItem(THEME_PRESET_KEY);
  return value === 'precision' || value === 'warm-paper' || value === 'darkroom' ? value : 'precision';
}

function getStoredLanguage(): LanguagePreference {
  if (typeof window === 'undefined') return 'zh-CN';
  const value = window.localStorage.getItem(LANGUAGE_KEY);
  return value === 'en-US' || value === 'zh-CN' ? value : 'zh-CN';
}

function applyTheme(themeMode: ThemeModePreference, themePreset: ThemePresetPreference) {
  const root = document.documentElement;
  const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const resolved = themeMode === 'system' ? (darkQuery.matches ? 'dark' : 'light') : themeMode;
  root.dataset.theme = resolved;
  root.dataset.themeMode = themeMode;
  root.dataset.themePreset = themePreset;
  root.style.colorScheme = resolved;
}

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [themeMode, setThemeModeState] = useState<ThemeModePreference>('system');
  const [themePreset, setThemePresetState] = useState<ThemePresetPreference>('precision');
  const [language, setLanguageState] = useState<LanguagePreference>('zh-CN');

  useEffect(() => {
    setThemeModeState(getStoredThemeMode());
    setThemePresetState(getStoredThemePreset());
    setLanguageState(getStoredLanguage());
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    applyTheme(themeMode, themePreset);
    const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => applyTheme(themeMode, themePreset);
    darkQuery.addEventListener('change', onChange);
    return () => darkQuery.removeEventListener('change', onChange);
  }, [themeMode, themePreset]);

  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<PreferencesContextValue>(() => {
    const dictionary = dictionaries[language] as Dictionary;
    return {
      themeMode,
      themePreset,
      language,
      setThemeMode(nextThemeMode) {
        window.localStorage.setItem(THEME_MODE_KEY, nextThemeMode);
        setThemeModeState(nextThemeMode);
      },
      setThemePreset(nextThemePreset) {
        window.localStorage.setItem(THEME_PRESET_KEY, nextThemePreset);
        setThemePresetState(nextThemePreset);
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
  }, [language, themeMode, themePreset]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error('usePreferences must be used inside PreferencesProvider');
  return context;
}
