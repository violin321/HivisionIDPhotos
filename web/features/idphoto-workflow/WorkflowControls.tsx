import type { BackgroundColor, IdPhotoTemplate } from '../../lib/api-client';
import { usePreferences } from '../../lib/preferences';

const backgroundMeta: Record<BackgroundColor, { swatch: string; labelKey: 'bgWhite' | 'bgBlue' | 'bgRed' | 'bgGray'; noteKey: 'bgWhiteNote' | 'bgBlueNote' | 'bgRedNote' | 'bgGrayNote' }> = {
  white: { swatch: '#f9f9f6', labelKey: 'bgWhite', noteKey: 'bgWhiteNote' },
  blue: { swatch: '#8fb7d6', labelKey: 'bgBlue', noteKey: 'bgBlueNote' },
  red: { swatch: '#b84a42', labelKey: 'bgRed', noteKey: 'bgRedNote' },
  gray: { swatch: '#c9c6bf', labelKey: 'bgGray', noteKey: 'bgGrayNote' },
};

const backgrounds: BackgroundColor[] = ['white', 'blue', 'red', 'gray'];

type WorkflowControlsProps = {
  templates: IdPhotoTemplate[];
  selectedTemplate: string;
  selectedBackground: BackgroundColor;
  aiPreview: boolean;
  canCreate: boolean;
  isWorking: boolean;
  onTemplateChange: (value: string) => void;
  onBackgroundChange: (value: BackgroundColor) => void;
  onAiPreviewChange: (value: boolean) => void;
  onCreateTask: () => void;
};

export function WorkflowControls({
  templates,
  selectedTemplate,
  selectedBackground,
  aiPreview,
  canCreate,
  isWorking,
  onTemplateChange,
  onBackgroundChange,
  onAiPreviewChange,
  onCreateTask,
}: WorkflowControlsProps) {
  const { t } = usePreferences();

  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_.9fr]">
      <section className="precision-card rounded-[24px] p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-slate">{t('specRuler')}</p>
            <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em]">{t('selectSpec')}</h3>
          </div>
          <span className="rounded-full border border-measurement/25 bg-measurement/10 px-3 py-1 font-mono text-[10px] text-measurement">/api/templates</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {templates.map((template) => {
            const active = template.templateId === selectedTemplate;
            return (
              <button
                key={template.templateId}
                type="button"
                aria-pressed={active}
                onClick={() => onTemplateChange(template.templateId)}
                className={`min-h-36 rounded-[20px] border p-4 text-left transition hover:-translate-y-0.5 ${
                  active ? 'border-measurement bg-measurement/10 shadow-lg shadow-measurement/10' : 'border-ink/10 bg-porcelain/70'
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-2xl font-semibold tracking-[-0.04em]">{template.label}</span>
                  <span className="font-mono text-[10px] text-slate">{template.size}</span>
                </div>
                <p className="mt-5 text-sm leading-5 text-graphite">{template.headRange}</p>
                <p className="mt-3 text-xs leading-5 text-slate">{template.printNote}</p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="precision-card rounded-[24px] p-5">
        <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-slate">{t('backgroundCassette')}</p>
        <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em]">{t('selectBackground')}</h3>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {backgrounds.map((background) => {
            const active = background === selectedBackground;
            const meta = backgroundMeta[background];
            return (
              <button
                key={background}
                type="button"
                aria-pressed={active}
                onClick={() => onBackgroundChange(background)}
                className={`rounded-[18px] border p-3 text-left transition hover:-translate-y-0.5 ${active ? 'border-amber bg-amber/10' : 'border-ink/10 bg-porcelain/70'}`}
              >
                <span className="block h-8 rounded-xl border border-ink/10" style={{ background: meta.swatch }} />
                <span className="mt-3 block font-semibold">{t(meta.labelKey)}</span>
                <span className="text-xs text-slate">{t(meta.noteKey)}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-4 rounded-[18px] border border-ink/10 bg-ink p-4 text-porcelain">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-[#b7c9cc]">{t('optionalBranch')}</p>
              <h4 className="mt-2 font-semibold">{t('aiEnhancePreview')}</h4>
              <p className="mt-2 text-xs leading-5 text-[#d8d1c4]">{t('aiComingSoon')}</p>
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-xs">
              <input type="checkbox" checked={aiPreview} onChange={(event) => onAiPreviewChange(event.target.checked)} disabled className="accent-amber" />
              {t('disabled')}
            </label>
          </div>
        </div>

        <button
          type="button"
          disabled={!canCreate || isWorking}
          onClick={onCreateTask}
          className="mt-4 w-full rounded-2xl bg-measurement px-5 py-4 text-sm font-semibold text-porcelain shadow-lg shadow-measurement/20 transition hover:-translate-y-0.5 hover:bg-[#185b63] disabled:cursor-not-allowed disabled:opacity-45"
        >
          {isWorking ? t('advancingTask') : t('createTask')}
        </button>
      </section>
    </div>
  );
}
