import type { ProcessingTask, TaskStatus } from '../../lib/api-client';
import { usePreferences } from '../../lib/preferences';

const statuses: TaskStatus[] = ['queued', 'processing', 'succeeded', 'failed', 'expired'];

const labelKeys: Record<TaskStatus, 'queued' | 'processing' | 'succeeded' | 'failed' | 'expired'> = {
  queued: 'queued',
  processing: 'processing',
  succeeded: 'succeeded',
  failed: 'failed',
  expired: 'expired',
};

const detailKeys: Record<TaskStatus, 'queuedDetail' | 'processingDetail' | 'succeededDetail' | 'failedDetail' | 'expiredDetail'> = {
  queued: 'queuedDetail',
  processing: 'processingDetail',
  succeeded: 'succeededDetail',
  failed: 'failedDetail',
  expired: 'expiredDetail',
};

type TaskStatusRailProps = {
  uploadReady: boolean;
  task: ProcessingTask | null;
  errorMessage?: string | null;
};

export function TaskStatusRail({ uploadReady, task, errorMessage }: TaskStatusRailProps) {
  const { t } = usePreferences();
  const displayStatus = task?.status ? t(labelKeys[task.status]) : t('idle');
  const currentIndex = task ? statuses.indexOf(task.status) : -1;

  return (
    <section className="rounded-[24px] border border-ink/10 bg-porcelain/78 p-4 shadow-sm sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-slate">03 · {t('taskModel')}</p>
          <h2 className="mt-1 text-lg font-semibold tracking-[-0.03em]">{displayStatus}</h2>
        </div>
        <span className={`h-2.5 w-2.5 rounded-full ${task?.status === 'failed' || task?.status === 'expired' ? 'bg-[#b84a42]' : task?.status === 'succeeded' ? 'bg-measurement' : task ? 'bg-amber' : 'bg-line'}`} />
      </div>

      <div className="mt-4 grid grid-cols-5 gap-1.5" aria-label={t('taskModel')}>
        {statuses.map((status, index) => {
          const active = task?.status === status;
          const complete = currentIndex > index && task?.status !== 'failed' && task?.status !== 'expired';
          return (
            <div key={status} className="min-w-0">
              <div className={`h-1.5 rounded-full ${active ? 'bg-amber' : complete ? 'bg-measurement' : 'bg-line'}`} />
              <p className={`mt-2 truncate text-[10px] font-semibold ${active ? 'text-ink' : 'text-slate'}`}>{t(labelKeys[status])}</p>
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs leading-5 text-slate">
        {task ? t(detailKeys[task.status]) : uploadReady ? t('materialReady') : t('publicProgressHint')}
      </p>

      {(task?.error || errorMessage) && (
        <div className="mt-4 rounded-2xl border border-[#b84a42]/25 bg-[#b84a42]/10 p-3 text-sm">
          <p className="font-semibold text-[#b84a42]">{task?.error?.code ?? 'CLIENT_ERROR'}</p>
          <p className="mt-1 leading-5 text-graphite">{task?.error?.message ?? errorMessage}</p>
        </div>
      )}
    </section>
  );
}
