import type { ProcessingTask, TaskStatus, UploadHandle } from '../../lib/api-client';

const statuses: TaskStatus[] = ['queued', 'processing', 'succeeded', 'failed', 'expired'];

const labels: Record<TaskStatus, string> = {
  queued: 'Queued',
  processing: 'Processing',
  succeeded: 'Succeeded',
  failed: 'Failed',
  expired: 'Expired',
};

type TaskStatusRailProps = {
  upload: UploadHandle | null;
  task: ProcessingTask | null;
};

export function TaskStatusRail({ upload, task }: TaskStatusRailProps) {
  return (
    <aside className="rounded-[28px] border border-ink/10 bg-porcelain/80 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-[-0.03em]">Task model</h2>
        <span className="rounded-full border border-measurement/25 bg-measurement/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-measurement">
          {task?.status ?? 'idle'}
        </span>
      </div>

      <div className="mt-6 space-y-3">
        {statuses.map((status, index) => {
          const currentIndex = task ? statuses.indexOf(task.status) : -1;
          const active = task?.status === status;
          const complete = currentIndex > index && task?.status !== 'failed' && task?.status !== 'expired';
          return (
            <div key={status} className="grid grid-cols-[22px_1fr] gap-3">
              <div className={`mt-1 h-3 w-3 rounded-full ${active ? 'bg-amber' : complete ? 'bg-measurement' : 'bg-line'}`} />
              <div className={`rounded-2xl border p-3 ${active ? 'border-amber bg-amber/10' : 'border-ink/10 bg-porcelain/60'}`}>
                <p className="text-sm font-semibold">{labels[status]}</p>
                <p className="mt-1 text-xs leading-5 text-slate">
                  {status === 'queued' && 'Task accepted; safe to poll rather than blocking request.'}
                  {status === 'processing' && 'Official crop, background, and compliance render are simulated.'}
                  {status === 'succeeded' && 'Result handles include fileId, previewUrl, downloadUrl, expiresAt.'}
                  {status === 'failed' && 'Contract reserves retryable error shape for server validation failures.'}
                  {status === 'expired' && 'Expiring handles keep web and miniapp behavior aligned.'}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      <dl className="mt-6 space-y-4 text-sm">
        <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-slate">uploadId</dt><dd className="max-w-40 truncate font-mono text-xs">{upload?.uploadId ?? '—'}</dd></div>
        <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-slate">fileId</dt><dd className="max-w-40 truncate font-mono text-xs">{upload?.fileId ?? '—'}</dd></div>
        <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-slate">taskId</dt><dd className="max-w-40 truncate font-mono text-xs">{task?.taskId ?? '—'}</dd></div>
        <div className="flex justify-between gap-4"><dt className="text-slate">platform</dt><dd className="font-mono text-xs">{task?.platform ?? 'web / miniapp-ready'}</dd></div>
      </dl>
    </aside>
  );
}
