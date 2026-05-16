import { useEffect, useMemo, useRef, useState } from 'react';
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
type PreviewTab = 'free' | 'pro';

type ResultPanelProps = {
  task: ProcessingTask | null;
  template?: IdPhotoTemplate;
  selectedBackground: BackgroundColor;
  generationKind?: GenerationKind;
};

type ProResultView = {
  item: AiProResult;
  providerStatus: string;
  qualityGateStatus: string;
  promptHash: string;
  fallbackToFree: boolean;
  isPassed: boolean;
  badge: string;
  warning: string;
  effectivePreviewUrl?: string | null;
  effectiveDownloadUrl?: string | null;
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

function buildProResultView(item: AiProResult): ProResultView {
  const providerStatus = String(item.promptMetadata?.providerStatus ?? item.status);
  const qualityGateStatus = String(item.promptMetadata?.qualityGateStatus ?? item.qualityGate?.status ?? 'not_run');
  const promptHash = String(item.promptMetadata?.promptHash ?? item.promptMetadata?.finalPromptHash ?? '—');
  const fallbackToFree = item.fallbackToFree === true || item.promptMetadata?.fallbackToFree === true || qualityGateStatus === 'quality_failed';
  const isPassed = qualityGateStatus === 'passed';
  const badge = fallbackToFree ? 'fallback_to_free' : isPassed ? 'quality_passed' : providerStatus;
  const fallbackReason = String(item.aiQualityReport?.fallbackReason ?? item.qualityGate?.fallbackReason ?? item.promptMetadata?.fallbackReason ?? '');
  const warning = fallbackToFree
    ? fallbackReason === 'AI_PRO_ASPECT_RATIO_MISMATCH'
      ? 'AI Pro 输出比例不符合证件照规格，已回退 Free Core。'
      : 'AI Pro 未通过质量门，已回退 Free Core。'
    : isPassed
      ? 'AI Pro 候选通过质量门，但仍需按提交平台要求人工核验。'
      : providerStatus === 'no_credentials'
        ? 'AI provider 未配置：当前展示 Free Core fallback，不影响官方结果。'
        : 'AI Pro 候选结果需人工核验。';
  return {
    item,
    providerStatus,
    qualityGateStatus,
    promptHash,
    fallbackToFree,
    isPassed,
    badge,
    warning,
    effectivePreviewUrl: item.previewUrl ?? item.imageUrl,
    effectiveDownloadUrl: item.downloadUrl,
  };
}


function aiProFallbackCopy(result: ProResultView): string {
  const reason = String(result.item.aiQualityReport?.fallbackReason ?? result.item.qualityGate?.fallbackReason ?? result.item.promptMetadata?.fallbackReason ?? '');
  if (reason === 'AI_PRO_ASPECT_RATIO_MISMATCH') {
    return 'AI Pro 输出比例不符合证件照规格，已回退 Free Core；当前默认保留 Free Core 预览，AI Pro 下载不作为独立结果提供。';
  }
  return 'AI Pro 未通过质量门，已回退 Free Core；当前默认保留 Free Core 预览，AI Pro 下载不作为独立结果提供。';
}

function resultTitle(item: AiProResult) {
  if (item.mode === 'ai_repair') return 'AI 精修';
  if (item.mode === 'ai_blue_formal_id_photo') return '证件照 AI 增强';
  return '高端影棚肖像';
}

export function ResultPanel({ task, template, selectedBackground, generationKind = 'idle' }: ResultPanelProps) {
  const { t } = usePreferences();
  const proResultViews = useMemo(() => (task?.proResults ?? []).map(buildProResultView), [task?.proResults]);
  const primaryProResult = proResultViews.find((item) => item.isPassed && !item.fallbackToFree) ?? proResultViews[0];
  const shouldShowProTab = Boolean(task?.aiPro?.enabled || proResultViews.length > 0);
  const proAvailable = Boolean(primaryProResult && !primaryProResult.fallbackToFree && primaryProResult.effectivePreviewUrl);
  const proFallback = Boolean(primaryProResult?.fallbackToFree);
  const proPassed = Boolean(primaryProResult?.isPassed && !primaryProResult.fallbackToFree);
  const freePreviewUrl = task?.officialResult?.previewUrl ?? task?.freeResult?.previewUrl;
  const freeDownloadUrl = task?.officialResult?.downloadUrl ?? task?.freeResult?.downloadUrl;
  const freeSucceeded = task?.status === 'succeeded' && Boolean(freePreviewUrl || freeDownloadUrl);
  const aiPreviewUrl = task?.aiEnhanceResult?.previewUrl;
  const aiKind = task?.options.aiEnhancePreviewKind ?? 'none';
  const taskId = task?.taskId ?? 'idle';
  const autoTab: PreviewTab = proPassed ? 'pro' : 'free';
  const [activeTab, setActiveTab] = useState<PreviewTab>(autoTab);
  const manualTaskRef = useRef<string | null>(null);
  const previousTaskRef = useRef<string | null>(null);

  useEffect(() => {
    const taskChanged = previousTaskRef.current !== taskId;
    if (taskChanged) {
      previousTaskRef.current = taskId;
      manualTaskRef.current = null;
    }
    if (manualTaskRef.current !== taskId) {
      setActiveTab(autoTab);
    }
  }, [autoTab, taskId]);

  useEffect(() => {
    if (activeTab === 'pro' && !proAvailable) {
      setActiveTab('free');
    }
  }, [activeTab, proAvailable]);

  const handleTabChange = (nextTab: PreviewTab) => {
    if (nextTab === 'pro' && !proAvailable) return;
    manualTaskRef.current = taskId;
    setActiveTab(nextTab);
  };

  const activePreviewUrl = activeTab === 'pro' ? primaryProResult?.effectivePreviewUrl : freePreviewUrl;
  const activeDownloadUrl = activeTab === 'pro' ? primaryProResult?.effectiveDownloadUrl : freeDownloadUrl;
  const activeDownloadDisabled = activeTab === 'pro' ? !proAvailable || !activeDownloadUrl : !freeSucceeded || !freeDownloadUrl;
  const activePreviewAlt = activeTab === 'pro' ? 'AI Pro 预览' : t('officialAlt');
  const activeSource = activeTab === 'pro' ? 'AI Pro candidate' : freeSucceeded ? 'IDCreator / Free Core' : '—';
  const statusBadge = activeTab === 'pro' ? 'AI PRO' : freeSucceeded ? t('ready') : t('waiting');
  const pluginResults = [
    task?.layoutResult ? { key: 'layout', title: t('layoutResult'), copy: t('layoutResultCopy'), result: task.layoutResult } : null,
    task?.compressedResult ? { key: 'compressed', title: t('compressedResult'), copy: t('compressedResultCopy', { kb: String(task.compressedTargetKb ?? task.options.imageKb ?? '—') }), result: task.compressedResult } : null,
    task?.watermarkedResult ? { key: 'watermarked', title: t('watermarkedResult'), copy: t('watermarkedResultCopy'), result: task.watermarkedResult } : null,
  ].filter(Boolean) as { key: string; title: string; copy: string; result: NonNullable<ProcessingTask['officialResult']> }[];

  return (
    <section className="rounded-[28px] border border-ink/10 bg-porcelain/80 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-slate">RESULT PREVIEW</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">证照结果预览</h2>
        </div>
        <span className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] ${activeTab === 'pro' ? 'border-amber/40 bg-amber/10 text-amber' : 'border-measurement/40 bg-measurement/10 text-measurement'}`}>
          {statusBadge}
        </span>
      </div>

      <GenerationProgress kind={generationKind} />

      <div className="mt-5 flex flex-wrap gap-2 rounded-[18px] border border-ink/10 bg-paper/55 p-1.5" role="tablist" aria-label="Result preview tabs">
        <button type="button" role="tab" aria-selected={activeTab === 'free'} onClick={() => handleTabChange('free')} className={`rounded-[14px] px-4 py-2 text-sm font-semibold transition ${activeTab === 'free' ? 'bg-ink text-porcelain shadow-lg shadow-ink/15' : 'text-graphite hover:bg-porcelain/70'}`}>Free Core 预览</button>
        <button type="button" role="tab" aria-selected={activeTab === 'pro'} aria-disabled={!proAvailable} disabled={!proAvailable} onClick={() => handleTabChange('pro')} className={`rounded-[14px] px-4 py-2 text-sm font-semibold transition ${activeTab === 'pro' ? 'bg-amber text-ink shadow-lg shadow-amber/15' : proAvailable ? 'text-graphite hover:bg-porcelain/70' : 'cursor-not-allowed text-slate/60'}`}>AI Pro 预览</button>
      </div>

      {proFallback && primaryProResult ? (
        <div className="mt-3 rounded-2xl border border-amber/30 bg-amber/10 p-3 text-xs leading-5 text-graphite">{aiProFallbackCopy(primaryProResult)}</div>
      ) : shouldShowProTab && !proAvailable ? (
        <div className="mt-3 rounded-2xl border border-amber/20 bg-paper/65 p-3 text-xs leading-5 text-slate">AI Pro 已开启，结果生成并通过质量门后会自动切到 AI Pro 预览；生成前默认显示 Free Core。</div>
      ) : null}

      <div className="mt-6 grid gap-5 lg:grid-cols-[190px_1fr]">
        <div className="relative mx-auto aspect-[3/4] w-full max-w-[210px] rounded-[22px] border border-ink/15 bg-[#ece6da] p-3 shadow-panel">
          <div className={`relative h-full rounded-[16px] border border-ink/10 bg-gradient-to-b ${backgroundClass[selectedBackground]}`}>
            {activePreviewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={activePreviewUrl} alt={activePreviewAlt} className="absolute inset-0 h-full w-full rounded-[16px] object-contain object-center" />
            ) : (
              <div className="absolute inset-x-[18%] bottom-0 flex h-[76%] flex-col items-center justify-end overflow-hidden rounded-[16px]">
                <div className="mb-[-6px] h-14 w-14 rounded-full border border-ink/10 bg-[#c9bca9]" />
                <div className="h-24 w-28 rounded-t-[48px] bg-[#2f3a40]" />
              </div>
            )}
            {!activePreviewUrl ? (
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
            <p className="text-sm leading-6 text-slate">{activeTab === 'pro' ? 'AI Pro 是可选增值支路，用于保守增强、换装、模板或形象照；只在通过质量门后作为候选预览展示，不替代 Free Core 官方结果。' : 'Free Core 使用 IDCreator/Hivision 标准证照主链路，本地确定性处理，是正式、稳定、免费的官方结果；AI Pro 失败不会影响此结果。'}</p>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('spec')}</dt><dd className="mt-1 font-semibold">{template?.label ?? '—'} · {template?.size ?? '—'}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('background')}</dt><dd className="mt-1 font-semibold">{t(backgroundLabelKeys[selectedBackground])}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">{t('resultSource')}</dt><dd className="mt-1 font-semibold">{activeSource}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">AI Pro 状态</dt><dd className="mt-1 font-semibold">{primaryProResult ? primaryProResult.badge : shouldShowProTab ? String((task?.stages?.aiPro as { status?: string } | undefined)?.status ?? 'queued') : t('disabled')}</dd></div>
            </dl>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <a aria-disabled={!activePreviewUrl} href={activePreviewUrl ?? '#'} className={`rounded-2xl px-4 py-3 text-sm font-semibold ${activePreviewUrl ? 'bg-ink text-porcelain' : 'pointer-events-none bg-line text-slate'}`}>打开 {activeTab === 'pro' ? 'AI Pro' : 'Free Core'} 预览</a>
            <a aria-disabled={activeDownloadDisabled} href={activeDownloadUrl ?? '#'} className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${!activeDownloadDisabled ? 'border-ink/15 text-ink' : 'pointer-events-none border-line text-slate'}`}>{activeTab === 'pro' ? '下载 AI Pro 结果' : '下载 Free Core 标准证照'}</a>
          </div>
        </div>
      </div>

      {primaryProResult ? (
        <div className="mt-5 rounded-[20px] border border-amber/25 bg-paper/70 p-4 text-sm leading-6 text-graphite">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-ink">AI Pro 质量门摘要 · {resultTitle(primaryProResult.item)}</p>
              <p className="text-xs text-slate">{primaryProResult.warning}</p>
            </div>
            <span className={`rounded-full border px-3 py-1 font-mono text-[10px] ${primaryProResult.fallbackToFree ? 'border-amber/35 text-amber' : 'border-measurement/35 text-measurement'}`}>{primaryProResult.badge}</span>
          </div>
          <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
            <div className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2"><dt className="text-slate">providerStatus</dt><dd className="mt-1 font-mono text-ink">{primaryProResult.providerStatus}</dd></div>
            <div className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2"><dt className="text-slate">qualityGate</dt><dd className="mt-1 font-mono text-ink">{primaryProResult.qualityGateStatus}</dd></div>
            <div className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2"><dt className="text-slate">result</dt><dd className="mt-1 font-mono text-ink">{primaryProResult.fallbackToFree ? 'Free Core fallback' : 'AI Pro candidate'}</dd></div>
            <div className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2"><dt className="text-slate">template</dt><dd className="mt-1 font-mono text-ink">{primaryProResult.item.promptTemplateId}@{primaryProResult.item.templateVersion}</dd></div>
            <div className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2"><dt className="text-slate">promptHash</dt><dd className="mt-1 break-all font-mono text-ink">{primaryProResult.promptHash}</dd></div>
            <div className="rounded-xl border border-ink/10 bg-paper/55 px-3 py-2"><dt className="text-slate">paid</dt><dd className="mt-1 font-mono text-ink">{primaryProResult.item.paid || primaryProResult.item.isPaidFeature ? 'Pro / 增值' : 'placeholder'}</dd></div>
          </dl>
          {primaryProResult.item.aiQualityReport ? (
            <div className="mt-3 rounded-xl border border-ink/10 bg-paper/60 px-3 py-2 text-xs">
              <span className="font-semibold text-ink">AI quality score</span>
              <span className="ml-2 font-mono text-ink">{primaryProResult.item.aiQualityReport.score}/100</span>
              {primaryProResult.item.aiQualityReport.fallbackReason ? <span className="ml-2 text-amber">{primaryProResult.item.aiQualityReport.fallbackReason}</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {task?.qualityReport ? (
        <details className={`mt-5 rounded-[20px] border p-4 text-sm leading-6 ${task.qualityReport.passed ? 'border-measurement/30 bg-measurement/10 text-graphite' : 'border-amber/30 bg-amber/10 text-graphite'}`}>
          <summary className="cursor-pointer font-semibold text-ink">{t('qualityReportTitle')} · {task.qualityReport.score}/100</summary>
          <p className="mt-2 text-xs text-slate">{task.qualityReport.passed ? t('qualityPassed') : t('qualityNeedsReview')}</p>
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
        </details>
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
