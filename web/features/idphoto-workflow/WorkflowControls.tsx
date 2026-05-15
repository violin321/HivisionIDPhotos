import { useMemo, useState } from 'react';
import type { AiProMode, BackgroundColor, IdPhotoTemplate, TaskOptions } from '../../lib/api-client';
import { usePreferences } from '../../lib/preferences';


function clampRgb(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(255, Math.round(value)));
}

function normalizeHex(value: string) {
  const raw = value.trim().replace(/^#/, '');
  if (/^[0-9a-fA-F]{3}$/.test(raw)) return `#${raw.split('').map((char) => `${char}${char}`).join('').toUpperCase()}`;
  if (/^[0-9a-fA-F]{6}$/.test(raw)) return `#${raw.toUpperCase()}`;
  return null;
}

function rgbToHex(rgb: [number, number, number]) {
  return `#${rgb.map((channel) => clampRgb(channel).toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

function hexToRgbTuple(value: string): [number, number, number] | null {
  const normalized = normalizeHex(value);
  if (!normalized) return null;
  return [1, 3, 5].map((start) => parseInt(normalized.slice(start, start + 2), 16)) as [number, number, number];
}

function currentCustomRgb(options: TaskOptions): [number, number, number] {
  const explicit = options.customBackgroundRgb;
  if (Array.isArray(explicit) && explicit.length === 3) return [clampRgb(Number(explicit[0])), clampRgb(Number(explicit[1])), clampRgb(Number(explicit[2]))];
  if (typeof explicit === 'object' && explicit) return [clampRgb(Number(explicit.r)), clampRgb(Number(explicit.g)), clampRgb(Number(explicit.b))];
  if (typeof explicit === 'string') {
    const parts = explicit.split(',').map((part) => clampRgb(Number(part.trim())));
    if (parts.length === 3) return parts as [number, number, number];
  }
  return hexToRgbTuple((options.customBackgroundHex as string | undefined) ?? '#626BCE') ?? [98, 107, 206];
}

const backgroundMeta: Record<BackgroundColor, { swatch: string; labelKey: 'bgWhite' | 'bgBlue' | 'bgRed' | 'bgGray'; noteKey: 'bgWhiteNote' | 'bgBlueNote' | 'bgRedNote' | 'bgGrayNote' }> = {
  white: { swatch: '#f9f9f6', labelKey: 'bgWhite', noteKey: 'bgWhiteNote' },
  blue: { swatch: '#8fb7d6', labelKey: 'bgBlue', noteKey: 'bgBlueNote' },
  red: { swatch: '#b84a42', labelKey: 'bgRed', noteKey: 'bgRedNote' },
  gray: { swatch: '#c9c6bf', labelKey: 'bgGray', noteKey: 'bgGrayNote' },
};

const backgrounds: BackgroundColor[] = ['white', 'blue', 'red', 'gray'];
const layoutPaperSizes = [
  { value: 'six-inch', label: '6 inch · 1205×1795' },
  { value: 'five-inch', label: '5 inch · 1051×1500' },
  { value: 'a4', label: 'A4 · 2479×3508' },
] as const;
const aiProModes: Array<{ value: AiProMode; label: string; note: string }> = [
  { value: 'ai_repair', label: 'AI 精修', note: 'fallback preview：轻量修复预览' },
  { value: 'ai_blue_formal_id_photo', label: 'AI 蓝底证件照', note: '可走已配置 AI Pro provider；无凭证时 fallback' },
  { value: 'executive_headshot', label: '高端影棚肖像', note: '非正式证件用途；当前 fallback preview' },
];
const templateCategories = ['all', 'common', 'exam', 'visa', 'credential'] as const;
type TemplateCategory = (typeof templateCategories)[number];

type WorkflowControlsProps = {
  templates: IdPhotoTemplate[];
  selectedTemplate: string;
  selectedBackground: BackgroundColor;
  aiPreview: boolean;
  canCreate: boolean;
  isWorking: boolean;
  taskOptions: TaskOptions;
  onTemplateChange: (value: string) => void;
  onBackgroundChange: (value: BackgroundColor) => void;
  onAiPreviewChange: (value: boolean) => void;
  onTaskOptionsChange: (patch: Partial<TaskOptions>) => void;
  onCreateTask: () => void;
};

function getTemplateCategory(template: IdPhotoTemplate): Exclude<TemplateCategory, 'all'> {
  const haystack = `${template.label} ${template.printNote} ${template.templateId}`;
  if (template.common) return 'common';
  if (/签证|visa|护照|passport/i.test(haystack)) return 'visa';
  if (/考试|教师|会计|四六级|计算机|研究生|公务员|exam/i.test(haystack)) return 'exam';
  return 'credential';
}

function TemplateCategoryPill({ template }: { template: IdPhotoTemplate }) {
  const { t } = usePreferences();
  const category = getTemplateCategory(template);
  const labelKey = category === 'visa' ? 'specCategoryVisa' : category === 'exam' ? 'specCategoryExam' : category === 'credential' ? 'specCategoryCredential' : 'specCategoryCommon';

  return <span className="rounded-full border border-ink/10 bg-paper/75 px-2 py-0.5 text-[10px] text-slate">{t(labelKey)}</span>;
}

function SpecSelectorDialog({
  open,
  templates,
  selectedTemplate,
  onClose,
  onTemplateChange,
}: {
  open: boolean;
  templates: IdPhotoTemplate[];
  selectedTemplate: string;
  onClose: () => void;
  onTemplateChange: (value: string) => void;
}) {
  const { t } = usePreferences();
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const [templateSearch, setTemplateSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<TemplateCategory>('all');

  const visibleTemplates = useMemo(() => {
    const keyword = templateSearch.trim().toLowerCase();
    return templates.filter((template) => {
      if (!showAllTemplates && !template.common) return false;
      if (activeCategory !== 'all' && getTemplateCategory(template) !== activeCategory) return false;
      if (!keyword) return true;
      return [template.label, template.size, template.printNote, template.headRange].join(' ').toLowerCase().includes(keyword);
    });
  }, [activeCategory, showAllTemplates, templateSearch, templates]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/45 px-0 pt-10 backdrop-blur-[3px] sm:items-center sm:px-5" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="spec-selector-title"
        className="relative flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-[32px] border border-porcelain/70 bg-paper shadow-2xl shadow-ink/30 sm:max-w-5xl sm:rounded-[32px]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-measurement/60 to-transparent" />
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink/10 bg-porcelain/70 p-5 sm:p-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-measurement">{t('specCatalog')}</p>
            <h3 id="spec-selector-title" className="mt-2 font-serif text-3xl leading-none tracking-[-0.05em] text-ink sm:text-4xl">{t('changeSpec')}</h3>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate">{t('specDialogHint')}</p>
          </div>
          <button type="button" onClick={onClose} aria-label={t('closeSpecSelector')} className="rounded-full border border-ink/10 bg-paper px-4 py-2 text-xs font-semibold text-graphite transition hover:-translate-y-0.5 hover:border-measurement/40">
            {t('closeSpecSelector')}
          </button>
        </div>

        <div className="border-b border-ink/10 bg-paper/95 p-4 sm:p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="flex rounded-full border border-ink/10 bg-porcelain/75 p-1">
              <button
                type="button"
                onClick={() => setShowAllTemplates(false)}
                className={`rounded-full px-4 py-2 text-xs font-semibold transition ${!showAllTemplates ? 'bg-measurement text-porcelain shadow-sm' : 'text-graphite hover:bg-paper'}`}
              >
                {t('commonSpecsOnly')}
              </button>
              <button
                type="button"
                onClick={() => setShowAllTemplates(true)}
                className={`rounded-full px-4 py-2 text-xs font-semibold transition ${showAllTemplates ? 'bg-amber text-ink shadow-sm' : 'text-graphite hover:bg-paper'}`}
              >
                {t('allSpecs')}
              </button>
            </div>
            <input
              value={templateSearch}
              onChange={(event) => setTemplateSearch(event.target.value)}
              placeholder={t('searchSpecs')}
              className="min-h-11 flex-1 rounded-2xl border border-ink/10 bg-porcelain/80 px-4 py-2 text-sm outline-none transition placeholder:text-slate/70 focus:border-measurement focus:bg-paper"
              autoFocus
            />
          </div>
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
            {templateCategories.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => setActiveCategory(category)}
                className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${activeCategory === category ? 'border-measurement bg-measurement/10 text-measurement' : 'border-ink/10 bg-porcelain/65 text-graphite hover:border-ink/20'}`}
              >
                {t(category === 'all' ? 'specCategoryAll' : category === 'common' ? 'specCategoryCommon' : category === 'exam' ? 'specCategoryExam' : category === 'visa' ? 'specCategoryVisa' : 'specCategoryCredential')}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleTemplates.map((template) => {
              const active = template.templateId === selectedTemplate;
              return (
                <button
                  key={template.templateId}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    onTemplateChange(template.templateId);
                    onClose();
                  }}
                  className={`group min-h-36 rounded-[22px] border p-4 text-left transition hover:-translate-y-0.5 ${
                    active ? 'border-measurement bg-measurement/10 shadow-lg shadow-measurement/10' : 'border-ink/10 bg-porcelain/70 hover:border-measurement/30 hover:bg-paper'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="text-2xl font-semibold tracking-[-0.04em] text-ink">{template.label}</span>
                    <div className="flex flex-col items-end gap-1">
                      <span className="font-mono text-[10px] text-slate">{template.size}</span>
                      <TemplateCategoryPill template={template} />
                    </div>
                  </div>
                  <p className="mt-5 text-sm leading-5 text-graphite">{template.headRange}</p>
                  <p className="mt-3 text-xs leading-5 text-slate">{template.printNote}</p>
                  <span className={`mt-4 inline-flex rounded-full px-3 py-1 text-[11px] font-semibold ${active ? 'bg-measurement text-porcelain' : 'bg-paper text-slate group-hover:text-measurement'}`}>{active ? t('selectedSpec') : t('selectThisSpec')}</span>
                </button>
              );
            })}
          </div>
          {visibleTemplates.length === 0 ? <div className="rounded-[22px] border border-dashed border-ink/15 bg-porcelain/60 p-8 text-center text-sm text-slate">{t('noSpecsFound')}</div> : null}
        </div>
      </section>
    </div>
  );
}

export function WorkflowControls({
  templates,
  selectedTemplate,
  selectedBackground,
  aiPreview,
  canCreate,
  isWorking,
  taskOptions,
  onTemplateChange,
  onBackgroundChange,
  onAiPreviewChange,
  onTaskOptionsChange,
  onCreateTask,
}: WorkflowControlsProps) {
  const { t } = usePreferences();
  const [selectorOpen, setSelectorOpen] = useState(false);
  const selectedTemplateInfo = useMemo(() => templates.find((template) => template.templateId === selectedTemplate) ?? templates[0], [selectedTemplate, templates]);
  const customImageKbEnabled = typeof taskOptions.imageKb === 'number' && Number.isFinite(taskOptions.imageKb);
  const watermarkEnabled = Boolean(taskOptions.watermarkEnabled);
  const printLayoutEnabled = Boolean(taskOptions.printLayoutEnabled);
  const customBackgroundEnabled = Boolean(taskOptions.customBackgroundEnabled);
  const customRgb = currentCustomRgb(taskOptions);
  const updateCustomHex = (value: string) => {
    const normalized = normalizeHex(value);
    onTaskOptionsChange({
      customBackgroundHex: value,
      customBackgroundRgb: normalized ? hexToRgbTuple(normalized) ?? undefined : taskOptions.customBackgroundRgb,
    });
  };
  const updateCustomRgbChannel = (index: 0 | 1 | 2, value: number) => {
    const nextRgb: [number, number, number] = [...customRgb] as [number, number, number];
    nextRgb[index] = clampRgb(value);
    onTaskOptionsChange({ customBackgroundRgb: nextRgb, customBackgroundHex: rgbToHex(nextRgb) });
  };

  return (
    <section className="workflow-step-card rounded-[26px] border border-ink/10 bg-porcelain/78 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 pb-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-measurement">02 · {t('selectSpec')}</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{t('specRuler')}</h3>
        </div>
        <span className="rounded-full border border-measurement/25 bg-measurement/10 px-3 py-1 font-mono text-[10px] text-measurement">{t('templateReadyBadge')}</span>
      </div>

      {selectedTemplateInfo ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(260px,.95fr)]">
          <div className="rounded-[24px] border border-measurement/20 bg-gradient-to-br from-porcelain via-paper to-measurement/10 p-4 shadow-inner shadow-measurement/5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-measurement">{t('currentSpec')}</p>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <h4 className="text-3xl font-semibold tracking-[-0.06em] text-ink sm:text-4xl">{selectedTemplateInfo.label}</h4>
                  <TemplateCategoryPill template={selectedTemplateInfo} />
                </div>
                <p className="mt-3 font-mono text-xs text-slate">{selectedTemplateInfo.size}</p>
                <p className="mt-3 max-w-xl text-sm leading-6 text-graphite">{selectedTemplateInfo.printNote}</p>
                <p className="mt-2 max-w-xl text-xs leading-5 text-slate">{selectedTemplateInfo.headRange}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectorOpen(true)}
                className="inline-flex shrink-0 items-center justify-center rounded-2xl border border-ink/10 bg-ink px-5 py-3 text-sm font-semibold text-porcelain shadow-lg shadow-ink/10 transition hover:-translate-y-0.5 hover:bg-measurement sm:min-w-32"
              >
                {t('changeSpec')}
              </button>
            </div>
            <p className="mt-4 text-xs leading-5 text-slate">{t('specSummaryHint')}</p>
          </div>

          <div className="rounded-[24px] border border-ink/10 bg-paper/50 p-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-slate">{t('backgroundCassette')}</p>
            <h4 className="mt-2 font-semibold tracking-[-0.03em]">{t('selectBackground')}</h4>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {backgrounds.map((background) => {
                const active = background === selectedBackground;
                const meta = backgroundMeta[background];
                return (
                  <button
                    key={background}
                    type="button"
                    aria-pressed={active}
                    onClick={() => onBackgroundChange(background)}
                    className={`rounded-[18px] border p-3 text-left transition hover:-translate-y-0.5 ${active ? 'border-amber bg-amber/10' : 'border-ink/10 bg-porcelain/70 hover:border-ink/20'}`}
                  >
                    <span className="block h-7 rounded-xl border border-ink/10" style={{ background: meta.swatch }} />
                    <span className="mt-2 block text-sm font-semibold">{t(meta.labelKey)}</span>
                    <span className="text-[11px] text-slate">{t(meta.noteKey)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}

      <div className="mt-4 rounded-[18px] border border-amber/25 bg-paper/60 p-4 text-graphite">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-amber">AI PRO · PROVIDER/FALLBACK</p>
            <h4 className="mt-1 font-semibold">上传时预选 AI Pro</h4>
            <p className="mt-1 text-xs leading-5 text-slate">AI 蓝底证件照会在后端尝试已配置 provider；无凭证或失败时显示 no_credentials / fallback，不影响官方结果。当前不产生真实支付。</p>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-slate">
            <input
              type="checkbox"
              checked={Boolean(taskOptions.aiPro?.enabled)}
              onChange={(event) => {
                const enabled = event.target.checked;
                onTaskOptionsChange({
                  aiPro: {
                    enabled,
                    modes: enabled ? (taskOptions.aiPro?.modes?.length ? taskOptions.aiPro.modes : ['ai_blue_formal_id_photo']) : [],
                    promptParams: taskOptions.aiPro?.promptParams ?? { outfit: '深色西装/白衬衫', backgroundColor: selectedBackground, style: 'natural', retouchLevel: 'medium' },
                    consentAccepted: enabled ? Boolean(taskOptions.aiPro?.consentAccepted) : false,
                  },
                });
                onAiPreviewChange(enabled);
              }}
              className="accent-amber"
            />
            开启 AI Pro
          </label>
        </div>

        {taskOptions.aiPro?.enabled ? (
          <div className="mt-4 space-y-4">
            <div className="grid gap-2 md:grid-cols-3">
              {aiProModes.map((mode) => {
                const active = taskOptions.aiPro?.modes?.includes(mode.value);
                return (
                  <label key={mode.value} className={`cursor-pointer rounded-2xl border p-3 text-sm transition ${active ? 'border-amber bg-amber/10' : 'border-ink/10 bg-porcelain/70'}`}>
                    <input
                      type="checkbox"
                      checked={Boolean(active)}
                      onChange={(event) => {
                        const current = taskOptions.aiPro?.modes ?? [];
                        const modes = event.target.checked ? [...new Set([...current, mode.value])] : current.filter((item) => item !== mode.value);
                        onTaskOptionsChange({ aiPro: { ...taskOptions.aiPro!, modes } });
                      }}
                      className="mr-2 accent-amber"
                    />
                    <span className="font-semibold">{mode.label}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate">{mode.note}</span>
                  </label>
                );
              })}
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <input type="text" value={(taskOptions.aiPro.promptParams.outfit as string | undefined) ?? ''} onChange={(event) => onTaskOptionsChange({ aiPro: { ...taskOptions.aiPro!, promptParams: { ...taskOptions.aiPro!.promptParams, outfit: event.target.value } } })} placeholder="服装：深色西装/白衬衫" className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" />
              <input type="text" value={(taskOptions.aiPro.promptParams.style as string | undefined) ?? ''} onChange={(event) => onTaskOptionsChange({ aiPro: { ...taskOptions.aiPro!, promptParams: { ...taskOptions.aiPro!.promptParams, style: event.target.value } } })} placeholder="风格：natural / studio" className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" />
              <select value={(taskOptions.aiPro.promptParams.retouchLevel as string | undefined) ?? 'medium'} onChange={(event) => onTaskOptionsChange({ aiPro: { ...taskOptions.aiPro!, promptParams: { ...taskOptions.aiPro!.promptParams, retouchLevel: event.target.value } } })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm">
                <option value="low">低强度</option>
                <option value="medium">中强度</option>
                <option value="high">高强度</option>
              </select>
            </div>
            <label className="flex items-start gap-2 rounded-2xl border border-dashed border-amber/35 bg-amber/5 px-3 py-3 text-xs leading-5 text-slate">
              <input type="checkbox" checked={Boolean(taskOptions.aiPro.consentAccepted)} onChange={(event) => onTaskOptionsChange({ aiPro: { ...taskOptions.aiPro!, consentAccepted: event.target.checked } })} className="mt-1 accent-amber" />
              我同意将图片用于 AI Pro 生成；若服务端配置了 provider，图片会提交到运行环境配置的第三方 AI 服务；否则使用 fallback。
            </label>
          </div>
        ) : null}
      </div>

      <SpecSelectorDialog open={selectorOpen} templates={templates} selectedTemplate={selectedTemplate} onClose={() => setSelectorOpen(false)} onTemplateChange={onTemplateChange} />

      <details className="mt-4 rounded-[18px] border border-ink/10 bg-paper/65 p-4">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 marker:hidden">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-slate">{t('advancedParams')}</p>
              <h4 className="mt-2 font-semibold text-ink">{t('advancedParamsTitle')}</h4>
              <p className="mt-2 text-xs leading-5 text-slate">{t('advancedParamsHint')}</p>
            </div>
            <span className="rounded-full border border-ink/10 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-slate">IDCreator ⌄</span>
          </summary>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('headMeasureRatio')}</span>
              <input type="number" min={0.1} max={0.5} step={0.01} value={taskOptions.headMeasureRatio ?? 0.2} onChange={(event) => onTaskOptionsChange({ headMeasureRatio: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('topDistance')}</span>
              <input type="number" min={0.02} max={0.5} step={0.01} value={taskOptions.topDistanceMax ?? taskOptions.topDistance ?? 0.12} onChange={(event) => onTaskOptionsChange({ topDistance: Number(event.target.value), topDistanceMax: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('outputDpi')}</span>
              <input type="number" min={72} max={600} step={1} value={taskOptions.dpi ?? 300} onChange={(event) => onTaskOptionsChange({ dpi: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('whiteningStrengthLabel')}</span>
              <input type="number" min={0} max={15} step={1} value={taskOptions.whiteningStrength ?? 0} onChange={(event) => onTaskOptionsChange({ whiteningStrength: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('brightnessStrengthLabel')}</span>
              <input type="number" min={-5} max={25} step={1} value={taskOptions.brightnessStrength ?? 0} onChange={(event) => onTaskOptionsChange({ brightnessStrength: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('contrastStrengthLabel')}</span>
              <input type="number" min={-10} max={50} step={1} value={taskOptions.contrastStrength ?? 0} onChange={(event) => onTaskOptionsChange({ contrastStrength: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('saturationStrengthLabel')}</span>
              <input type="number" min={-10} max={50} step={1} value={taskOptions.saturationStrength ?? 0} onChange={(event) => onTaskOptionsChange({ saturationStrength: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
            <label className="text-sm text-graphite">
              <span className="mb-1 block font-medium">{t('sharpenStrengthLabel')}</span>
              <input type="number" min={0} max={5} step={1} value={taskOptions.sharpenStrength ?? 0} onChange={(event) => onTaskOptionsChange({ sharpenStrength: Number(event.target.value) })} className="w-full rounded-xl border border-ink/10 bg-porcelain px-3 py-2" />
            </label>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm">
              <input type="checkbox" checked={customImageKbEnabled} onChange={(event) => onTaskOptionsChange({ imageKb: event.target.checked ? (taskOptions.imageKb ?? 50) : undefined, imageKbMode: taskOptions.imageKbMode ?? 'exact' })} className="accent-measurement" />
              {t('imageKbLabel')}
            </label>
            <input type="number" min={10} max={1000} step={1} value={customImageKbEnabled ? taskOptions.imageKb ?? 50 : ''} disabled={!customImageKbEnabled} onChange={(event) => onTaskOptionsChange({ imageKb: Number(event.target.value) })} placeholder="50" className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm disabled:opacity-45" />
            <select value={(taskOptions.imageKbMode as string | undefined) ?? 'exact'} disabled={!customImageKbEnabled} onChange={(event) => onTaskOptionsChange({ imageKbMode: event.target.value as 'exact' | 'max' })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm disabled:opacity-45" aria-label={t('imageKbModeLabel')}>
              <option value="exact">{t('imageKbModeExact')}</option>
              <option value="max">{t('imageKbModeMax')}</option>
            </select>
            <div className="rounded-2xl border border-dashed border-measurement/25 bg-measurement/5 px-3 py-3 text-xs leading-5 text-slate">{t('imageKbReadyHint')}</div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm">
              <input type="checkbox" checked={watermarkEnabled} onChange={(event) => onTaskOptionsChange({ watermarkEnabled: event.target.checked, watermarkText: event.target.checked ? (taskOptions.watermarkText as string | undefined) ?? '仅供证件照使用' : taskOptions.watermarkText })} className="accent-measurement" />
              {t('watermarkLabel')}
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm">
              <input type="checkbox" checked={printLayoutEnabled} onChange={(event) => onTaskOptionsChange({ printLayoutEnabled: event.target.checked, layoutPaperSize: event.target.checked ? (taskOptions.layoutPaperSize as 'six-inch' | 'five-inch' | 'a4' | undefined) ?? 'six-inch' : taskOptions.layoutPaperSize, printLayoutSize: event.target.checked ? (taskOptions.printLayoutSize as 'six-inch' | 'five-inch' | 'a4' | undefined) ?? 'six-inch' : taskOptions.printLayoutSize })} className="accent-measurement" />
              {t('printLayoutLabel')}
            </label>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <label className="text-sm text-graphite md:col-span-2">
              <span className="mb-1 block font-medium">{t('renderModeLabel')}</span>
              <select value={(taskOptions.renderMode as string | undefined) ?? 'solid'} onChange={(event) => onTaskOptionsChange({ renderMode: event.target.value as 'solid' | 'upDownGradientWhite' | 'centerGradientWhite' })} className="w-full rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm">
                <option value="solid">{t('renderModeSolid')}</option>
                <option value="upDownGradientWhite">{t('renderModeUpDown')}</option>
                <option value="centerGradientWhite">{t('renderModeCenter')}</option>
              </select>
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm">
              <input type="checkbox" checked={Boolean(taskOptions.horizontalFlip)} onChange={(event) => onTaskOptionsChange({ horizontalFlip: event.target.checked })} className="accent-measurement" />
              {t('horizontalFlipLabel')}
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm">
              <input type="checkbox" checked={Boolean(taskOptions.faceAlign)} onChange={(event) => onTaskOptionsChange({ faceAlign: event.target.checked })} className="accent-measurement" />
              {t('faceAlignLabel')}
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm">
              <input type="checkbox" checked={Boolean(taskOptions.jpegFormat)} onChange={(event) => onTaskOptionsChange({ jpegFormat: event.target.checked })} className="accent-measurement" />
              {t('jpegFormatLabel')}
            </label>
            <label className="flex items-center gap-2 rounded-2xl border border-ink/10 bg-porcelain/80 px-3 py-3 text-sm md:col-span-2">
              <input type="checkbox" checked={customBackgroundEnabled} onChange={(event) => onTaskOptionsChange({ customBackgroundEnabled: event.target.checked })} className="accent-measurement" />
              {t('customBackgroundLabel')}
            </label>
            <input type="color" value={normalizeHex((taskOptions.customBackgroundHex as string | undefined) ?? '#626BCE') ?? '#626BCE'} disabled={!customBackgroundEnabled} onChange={(event) => updateCustomHex(event.target.value)} className="h-[46px] w-full rounded-2xl border border-ink/10 bg-porcelain px-2 py-2 disabled:opacity-45" aria-label={t('customBackgroundHex')} />
            <input type="text" value={(taskOptions.customBackgroundHex as string | undefined) ?? '#626BCE'} disabled={!customBackgroundEnabled} onChange={(event) => updateCustomHex(event.target.value)} placeholder="#626BCE" className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm disabled:opacity-45" aria-label={t('customBackgroundHex')} />
            <div className="grid gap-2 md:col-span-4 md:grid-cols-3">
              {(['R', 'G', 'B'] as const).map((channel, index) => (
                <label key={channel} className="text-xs text-slate">
                  <span className="mb-1 block font-mono">{t('customBackgroundRgb')} · {channel}</span>
                  <input type="number" min={0} max={255} step={1} value={customRgb[index]} disabled={!customBackgroundEnabled} onChange={(event) => updateCustomRgbChannel(index as 0 | 1 | 2, Number(event.target.value))} className="w-full rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm text-graphite disabled:opacity-45" />
                </label>
              ))}
            </div>
          </div>
          {printLayoutEnabled ? (
            <div className="mt-3 grid gap-3 md:grid-cols-[180px_1fr]">
              <select value={(taskOptions.layoutPaperSize as string | undefined) ?? 'six-inch'} onChange={(event) => onTaskOptionsChange({ layoutPaperSize: event.target.value as 'six-inch' | 'five-inch' | 'a4', printLayoutSize: event.target.value as 'six-inch' | 'five-inch' | 'a4', fiveInchPaper: event.target.value === 'five-inch' })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" aria-label={t('layoutPaperSizeLabel')}>
                {layoutPaperSizes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
              <label className="flex items-center gap-2 rounded-2xl border border-dashed border-measurement/25 bg-measurement/5 px-3 py-3 text-xs leading-5 text-slate">
                <input type="checkbox" checked={Boolean(taskOptions.layoutCropLine)} onChange={(event) => onTaskOptionsChange({ layoutCropLine: event.target.checked })} className="accent-measurement" />
                {t('layoutCropLineLabel')} · {t('layoutPaperSizeHint')}
              </label>
            </div>
          ) : null}
          {watermarkEnabled ? (
            <div className="mt-3 grid gap-3 md:grid-cols-[1fr_150px_repeat(4,minmax(92px,1fr))]">
              <input type="text" value={(taskOptions.watermarkText as string | undefined) ?? '仅供证件照使用'} onChange={(event) => onTaskOptionsChange({ watermarkText: event.target.value })} placeholder="仅供证件照使用" className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" />
              <input type="color" value={(taskOptions.watermarkTextColor as string | undefined) ?? '#8B8B1B'} onChange={(event) => onTaskOptionsChange({ watermarkTextColor: event.target.value })} className="h-[46px] w-full rounded-2xl border border-ink/10 bg-porcelain px-2 py-2" aria-label={t('watermarkColor')} />
              <input type="number" min={8} max={160} step={1} value={(taskOptions.watermarkTextSize as number | undefined) ?? 32} onChange={(event) => onTaskOptionsChange({ watermarkTextSize: Number(event.target.value) })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" aria-label={t('watermarkSize')} placeholder={t('watermarkSize')} />
              <input type="number" min={0.05} max={1} step={0.05} value={(taskOptions.watermarkTextOpacity as number | undefined) ?? 0.35} onChange={(event) => onTaskOptionsChange({ watermarkTextOpacity: Number(event.target.value) })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" aria-label={t('watermarkOpacity')} placeholder={t('watermarkOpacity')} />
              <input type="number" min={-90} max={90} step={1} value={(taskOptions.watermarkTextAngle as number | undefined) ?? 30} onChange={(event) => onTaskOptionsChange({ watermarkTextAngle: Number(event.target.value) })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" aria-label={t('watermarkAngle')} placeholder={t('watermarkAngle')} />
              <input type="number" min={10} max={300} step={1} value={(taskOptions.watermarkTextSpace as number | undefined) ?? 75} onChange={(event) => onTaskOptionsChange({ watermarkTextSpace: Number(event.target.value) })} className="rounded-2xl border border-ink/10 bg-porcelain px-3 py-3 text-sm" aria-label={t('watermarkSpace')} placeholder={t('watermarkSpace')} />
            </div>
          ) : null}
          <div className="mt-3 rounded-2xl border border-dashed border-measurement/25 bg-measurement/5 px-4 py-3 text-xs leading-5 text-graphite">{t('connectedFeaturesHint')}</div>
      </details>

      <button
        type="button"
        disabled={!canCreate || isWorking}
        onClick={onCreateTask}
        className="mt-4 w-full rounded-2xl bg-measurement px-5 py-4 text-sm font-semibold text-porcelain shadow-lg shadow-measurement/20 transition hover:-translate-y-0.5 hover:bg-[#185b63] disabled:cursor-not-allowed disabled:opacity-45"
      >
        03 · {isWorking ? t('advancingTask') : t('createTask')}
      </button>
    </section>
  );
}
