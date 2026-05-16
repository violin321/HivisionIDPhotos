import type { AiProResult, BackgroundColor, IdPhotoTemplate, ProcessingTask } from '../../lib/api-client';
import { usePreferences } from '../../lib/preferences';

const backgroundClass: Record<BackgroundColor, string> = {
  white: 'from-[#ffffff] to-[#f2f1ed]',
  blue: 'from-[#cde3f1] to-[#8fb7d6]',
  red: 'from-[#e8a39c] to-[#b84a42]',
  gray: 'from-[#e2dfd8] to-[#bdb8ae]',
};

const backgroundLabelKeys: Record<BackgroundColor, 'bgWhite' | 'bgBlue' | 'bgRed' | 'bgGray'> = {
  white: 'bgWhite',
  blue: 'bgBlue',
  red: 'bgRed',
  gray: 'bgGray',
};

function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function qualityMetricSummary(metrics: Record<string, unknown> | undefined) {
  const dimensions = metrics?.dimensions as { match?: boolean; actual?: { width?: number; height?: number } } | undefined;
  const face = metrics?.face as { count?: number | null } | undefined;
  const composition = metrics?.composition as { topDistanceRatio?: number; horizontalCenterOffset?: number } | undefined;
  const backgroundColor = metrics?.backgroundColor as { meanDelta?: number } | undefined;
  return [
    { label: '尺寸', value: dimensions?.actual ? `${dimensions.actual.width ?? '—'}×${dimensions.actual.height ?? '—'}` : formatMetricValue(dimensions?.match) },
    { label: '人脸', value: face?.count === 1 ? '1' : formatMetricValue(face?.count) },
    { label: '顶部距离', value: formatMetricValue(composition?.topDistanceRatio) },
    { label: '水平偏移', value: formatMetricValue(composition?.horizontalCenterOffset) },
    { label: '背景Δ', value: formatMetricValue(backgroundColor?.meanDelta) },
  ];
}

type GenerationKind = 'idle' | 'idcreator' | 'ai-pro';

type ResultPanelProps = {
  task: ProcessingTask | null;
  template?: IdPhotoTemplate;
  selectedBackground: BackgroundColor;
  generationKind?: GenerationKind;
};

function GenerationProgress({ kind }: { kind: GenerationKind }) {
  if (kind === 'idle') return null;
  const isAiPro = kind === 'ai-pro';
  return (
    <div className={`mt-5 overflow-hidden rounded-[20px] border ${isAiPro ? 'border-amber/40 bg-amber/10' : 'border-measurement/25 bg-measurement/10'}`} role="status" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <span className={`h-4 w-4 animate-spin rounded-full border-2 border-transparent ${isAiPro ? 'border-t-amber border-r-amber' : 'border-t-measurement border-r-measurement'}`} aria-hidden="true" />
          <div>
            <p className="font-semibold text-ink">{isAiPro ? 'AI Pro 生成中' : '证件照生成中…'}</p>
            <p className="mt-0.5 text-xs text-slate">{isAiPro ? '预计 30–120 秒；完成后先经过质量门，不合格会回退 Free Core。' : '正在处理 IDCreator 官方结果。'}</p>
          </div>
        </div>
        <span className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${isAiPro ? 'border-amber/35 text-amber' : 'border-measurement/35 text-measurement'}`}>{isAiPro ? 'AI PRO' : 'IDCREATOR'}</span>
      </div>
      <div className="h-1.5 bg-paper/70">
        <div className={`h-full w-2/3 animate-pulse rounded-r-full ${isAiPro ? 'bg-amber' : 'bg-measurement'}`} />
      </div>
    </div>
  );
}

function resultTitle(item: AiProResult) {
  if (item.mode === 'ai_repair') return 'AI 精修';
  if (item.mode === 'ai_blue_formal_id_photo') return '证件照 AI 增强';
  return '高端影棚肖像';
}

export function ResultPanel({ task, template, selectedBackground, generationKind = 'idle' }: ResultPanelProps) {
  const { t } = usePreferences();
  const proResults = task?.proResults ?? [];
  const shouldShowProSection = Boolean(task?.aiPro?.enabled || proResults.length > 0);
  const freePreviewUrl = task?.officialResult?.previewUrl ?? task?.freeResult?.previewUrl;
  const freeDownloadUrl = task?.officialResult?.downloadUrl ?? task?.freeResult?.downloadUrl;
  const freeSucceeded = task?.status === 'succeeded' && Boolean(freePreviewUrl || freeDownloadUrl);
  const aiPreviewUrl = task?.aiEnhanceResult?.previewUrl;
  const aiKind = task?.options.aiEnhancePreviewKind ?? 'none';
  const pluginResults = [
    task?.layoutResult ? { key: 'layout', title: t('layoutResult'), copy: t('layoutResultCopy'), result: task.layoutResult } : null,
    task?.compressedResult ? { key: 'compressed', title: t('compressedResult'), copy: t('compressedResultCopy', { kb: String(task.compressedTargetKb ?? task.options.imageKb ?? '—') }), result: task.compressedResult } : null,
    task?.watermarkedResult ? { key: 'watermarked', title: t('watermarkedResult'), copy: t('watermarkedResultCopy'), result: task.watermarkedResult } : null,
  ].filter(Boolean) as { key: string; title: string; copy: string; result: NonNullable<ProcessingTask['officialResult']> }[];

  return (
    <section className="rounded-[28px] border border-ink/10 bg-porcelain/80 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-slate">FREE CORE / IDCREATOR</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">Free Core 标准证照</h2>
        </div>
        <span className="rounded-full border border-measurement/40 bg-measurement/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-measurement">
          {freeSucceeded ? t('ready') : t('waiting')}
        </span>
      </div>

      <GenerationProgress kind={generationKind} />

      <div className="mt-6 grid gap-5 lg:grid-cols-[190px_1fr]">
        <div className="relative mx-auto aspect-[3/4] w-full max-w-[210px] rounded-[22px] border border-ink/15 bg-[#ece6da] p-3 shadow-panel">
          <div className={`relative h-full rounded-[16px] border border-ink/10 bg-gradient-to-b ${backgroundClass[selectedBackground]}`}>
            {freePreviewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={freePreviewUrl} alt={t('officialAlt')} className="absolute inset-0 h-full w-full rounded-[16px] object-contain object-center" />
            ) : (
              <div className="absolute inset-x-[18%] bottom-0 flex h-[76%] flex-col items-center justify-end overflow-hidden rounded-[16px]">
                <div className="mb-[-6px] h-14 w-14 rounded-full border border-ink/10 bg-[#c9bca9]" />
                <div className="h-24 w-28 rounded-t-[48px] bg-[#2f3a40]" />
              </div>
            )}
            {!freePreviewUrl ? (
              <>
                <div className="pointer-events-none absolute inset-x-3 top-[24%] border-t border-measurement/30" />
                <div className="pointer-events-none absolute inset-x-3 top-[38%] border-t border-measurement/20" />
                <div className="pointer-events-none absolute inset-y-3 left-1/2 border-l border-measurement/20" />
              </>
            ) : null}
          </div>
        </div>

        <div className="flex flex-col justify-between">
          <div>
            <p className="text-sm leading-6 text-slate">Free Core 使用 IDCreator/Hivision 标准证照主链路，本地确定性处理，是正式、稳定、免费的官方结果；AI Pro 失败不会影响此结果。</p>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('spec')}</dt><dd className="mt-1 font-semibold">{template?.label ?? '—'} · {template?.size ?? '—'}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('background')}</dt><dd className="mt-1 font-semibold">{t(backgroundLabelKeys[selectedBackground])}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('resultSource')}</dt><dd className="mt-1 font-semibold">{freeSucceeded ? 'IDCreator / Free Core' : '—'}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('aiPreview')}</dt><dd className="mt-1 font-semibold">{aiKind === 'none' ? t('disabled') : aiKind}</dd></div>
            </dl>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <a aria-disabled={!freeSucceeded} href={freePreviewUrl ?? '#'} className={`rounded-2xl px-4 py-3 text-sm font-semibold ${freeSucceeded && freePreviewUrl ? 'bg-ink text-porcelain' : 'pointer-events-none bg-line text-slate'}`}>打开 Free Core 预览</a>
            <a aria-disabled={!freeSucceeded} href={freeDownloadUrl ?? '#'} className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${freeSucceeded && freeDownloadUrl ? 'border-ink/15 text-ink' : 'pointer-events-none border-line text-slate'}`}>下载 Free Core 标准证照</a>
          </div>
        </div>
      </div>

      {task?.qualityReport ? (
        <div className={`mt-5 rounded-[20px] border p-4 text-sm leading-6 ${task.qualityReport.passed ? 'border-measurement/30 bg-measurement/10 text-graphite' : 'border-amber/30 bg-amber/10 text-graphite'}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-ink">{t('qualityReportTitle')}</p>
              <p className="text-xs text-slate">{task.qualityReport.passed ? t('qualityPassed') : t('qualityNeedsReview')}</p>
            </div>
            <span className="rounded-full border border-ink/10 bg-porcelain/70 px-3 py-1 font-mono text-xs text-ink">{task.qualityReport.score}/100</span>
          </div>
          <dl className="mt-3 grid gap-2 sm:grid-cols-5">
            {qualityMetricSummary(task.qualityReport.metrics).map((metric) => (
              <div key={metric.label} className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2">
                <dt className="text-[11px] text-slate">{metric.label}</dt>
                <dd className="mt-1 font-mono text-xs text-ink">{metric.value}</dd>
              </div>
            ))}
          </dl>
          {[...task.qualityReport.errors, ...task.qualityReport.warnings].length ? (
            <ul className="mt-3 list-disc pl-5">
              {[...task.qualityReport.errors, ...task.qualityReport.warnings].slice(0, 4).map((issue) => <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>)}
            </ul>
          ) : null}
          {task.qualityReport.suggestions.length ? (
            <ul className="mt-3 list-disc pl-5 text-slate">
              {task.qualityReport.suggestions.slice(0, 3).map((suggestion) => <li key={suggestion}>{suggestion}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}

      {task?.warnings?.length ? (
        <div className="mt-5 rounded-[20px] border border-amber/30 bg-amber/10 p-4 text-sm leading-6 text-graphite">
          <p className="font-semibold text-ink">{t('pluginWarnings')}</p>
          <ul className="mt-2 list-disc pl-5">
            {task.warnings.map((warning) => <li key={`${warning.code}-${warning.message}`}>{warning.message}</li>)}
          </ul>
        </div>
      ) : task?.warning ? (
        <div className="mt-5 rounded-[20px] border border-amber/30 bg-amber/10 p-4 text-sm leading-6 text-graphite">{task.warning.message}</div>
      ) : null}

      {pluginResults.length > 0 ? (
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {pluginResults.map((item) => (
            <div key={item.key} className="rounded-[20px] border border-ink/10 bg-paper/70 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-measurement">{item.title}</p>
              <p className="mt-2 min-h-10 text-xs leading-5 text-slate">{item.copy}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <a href={item.result.previewUrl} className="rounded-xl bg-ink px-3 py-2 text-xs font-semibold text-porcelain">{t('signedPreview')}</a>
                <a href={item.result.downloadUrl} className="rounded-xl border border-ink/15 px-3 py-2 text-xs font-semibold text-ink">{t('signedDownload')}</a>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {shouldShowProSection ? (
        <div className="mt-5 rounded-[20px] border border-amber/30 bg-amber/10 p-4 text-sm leading-6 text-graphite">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-ink">AI Pro 增值结果</p>
              <p className="text-xs text-slate">AI Pro 是可选增值支路，用于保守增强、换装、模板或形象照；不替代 Free Core 标准证照。</p>
            </div>
            <span className="rounded-full border border-amber/40 bg-paper/70 px-3 py-1 font-mono text-[10px] text-amber">{String((task?.stages?.aiPro as { status?: string } | undefined)?.status ?? 'queued')}</span>
          </div>
          {proResults.length === 0 ? (
            <p className="mt-3 rounded-2xl border border-amber/20 bg-paper/65 p-3 text-xs text-slate">AI Pro 已开启，结果生成后会在这里单独展示；Free Core 下载始终保留在上方。</p>
          ) : (
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              {proResults.map((item) => {
                const providerStatus = String(item.promptMetadata?.providerStatus ?? item.status);
                const qualityGateStatus = String(item.promptMetadata?.qualityGateStatus ?? item.qualityGate?.status ?? 'not_run');
                const promptHash = String(item.promptMetadata?.promptHash ?? item.promptMetadata?.finalPromptHash ?? '—');
                const fallbackToFree = item.fallbackToFree === true || item.promptMetadata?.fallbackToFree === true || qualityGateStatus === 'quality_failed';
                const isPassed = qualityGateStatus === 'passed';
                const badge = fallbackToFree ? 'fallback_to_free' : isPassed ? 'quality_passed' : providerStatus;
                const warning = fallbackToFree
                  ? 'AI Pro 结果未通过质量门，已回退到 Free Core 结果；这不代表 AI 成功替换官方结果。'
                  : isPassed
                    ? 'AI Pro 候选通过质量门，但仍需按提交平台要求人工核验。'
                    : providerStatus === 'no_credentials'
                      ? 'AI provider 未配置：当前展示 Free Core fallback，不影响官方结果。'
                      : 'AI Pro 候选结果需人工核验。';
                return (
                  <div key={`${item.mode}-${item.promptTemplateId}`} className={`rounded-[18px] border p-3 ${fallbackToFree ? 'border-amber/35 bg-paper/70' : 'border-measurement/30 bg-measurement/10'}`}>
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-semibold text-ink">{resultTitle(item)}</p>
                      <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] ${fallbackToFree ? 'border-amber/35 text-amber' : 'border-measurement/35 text-measurement'}`}>{badge}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate">{warning}</p>
                    <dl className="mt-2 space-y-1 text-xs text-slate">
                      <div><dt className="inline">provider</dt><dd className="ml-2 inline font-mono text-ink">{String(item.promptMetadata?.provider ?? 'mock')}</dd></div>
                      <div><dt className="inline">providerStatus</dt><dd className="ml-2 inline font-mono text-ink">{providerStatus}</dd></div>
                      <div><dt className="inline">qualityGate</dt><dd className="ml-2 inline font-mono text-ink">{qualityGateStatus}</dd></div>
                      <div><dt className="inline">template</dt><dd className="ml-2 inline font-mono text-ink">{item.promptTemplateId}@{item.templateVersion}</dd></div>
                      <div><dt className="inline">promptHash</dt><dd className="ml-2 inline font-mono text-ink">{promptHash}</dd></div>
                      <div><dt className="inline">result</dt><dd className="ml-2 inline font-mono text-ink">{fallbackToFree ? 'Free Core fallback' : 'AI Pro candidate'}</dd></div>
                      <div><dt className="inline">paid</dt><dd className="ml-2 inline font-mono text-ink">{item.paid || item.isPaidFeature ? 'Pro / 增值' : 'placeholder'}</dd></div>
                    </dl>
                    {item.aiQualityReport ? (
                      <div className="mt-2 rounded-xl border border-ink/10 bg-paper/60 px-3 py-2 text-xs">
                        <span className="font-semibold text-ink">AI quality score</span>
                        <span className="ml-2 font-mono text-ink">{item.aiQualityReport.score}/100</span>
                        {item.aiQualityReport.fallbackReason ? <span className="ml-2 text-amber">{item.aiQualityReport.fallbackReason}</span> : null}
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.previewUrl ? <a href={item.previewUrl} className="inline-block rounded-xl bg-ink px-3 py-2 text-xs font-semibold text-porcelain">{fallbackToFree ? '打开 Free fallback 预览' : '打开 AI Pro 预览'}</a> : null}
                      {item.downloadUrl ? <a href={item.downloadUrl} className="inline-block rounded-xl border border-ink/15 px-3 py-2 text-xs font-semibold text-ink">{fallbackToFree ? '下载 Free fallback' : '下载 AI Pro 结果'}</a> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : null}

      {aiPreviewUrl && (
        <div className="mt-5 rounded-[20px] border border-ink/10 bg-ink p-4 text-porcelain">
          <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-[#b7c9cc]">{t('aiLane')}</p>
          <p className="mt-2 text-sm leading-6 text-[#d8d1c4]">{t('aiLaneCopy', { kind: aiKind })}</p>
          <a href={aiPreviewUrl} className="mt-3 inline-block rounded-2xl border border-[#d8d1c4]/30 px-4 py-2 text-sm font-semibold text-porcelain">
            {t('openLocalPreview')}
          </a>
        </div>
      )}
    </section>
  );
}
