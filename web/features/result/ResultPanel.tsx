import type { BackgroundColor, IdPhotoTemplate, ProcessingTask } from '../../lib/api-client';

const backgroundClass: Record<BackgroundColor, string> = {
  white: 'from-[#ffffff] to-[#f2f1ed]',
  blue: 'from-[#cde3f1] to-[#8fb7d6]',
  red: 'from-[#e8a39c] to-[#b84a42]',
  gray: 'from-[#e2dfd8] to-[#bdb8ae]',
};

type ResultPanelProps = {
  task: ProcessingTask | null;
  template?: IdPhotoTemplate;
  selectedBackground: BackgroundColor;
  sourcePreviewUrl: string | null;
};

export function ResultPanel({ task, template, selectedBackground, sourcePreviewUrl }: ResultPanelProps) {
  const succeeded = task?.status === 'succeeded' && task.officialResult;

  return (
    <section className="rounded-[28px] border border-ink/10 bg-porcelain/80 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-slate">Official result</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">Certificate output card</h2>
        </div>
        <span className="rounded-full border border-amber/40 bg-amber/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-amber">
          {succeeded ? 'ready' : 'waiting'}
        </span>
      </div>

      <div className="mt-6 grid gap-5 md:grid-cols-[190px_1fr]">
        <div className="relative mx-auto aspect-[3/4] w-full max-w-[190px] rounded-[22px] border border-ink/15 bg-[#ece6da] p-3 shadow-panel">
          <div className="absolute -left-5 top-8 h-36 w-4 border-y border-ink/25"><div className="ruler-edge h-full opacity-70" /></div>
          <div className={`relative h-full overflow-hidden rounded-[16px] border border-ink/10 bg-gradient-to-b ${backgroundClass[selectedBackground]}`}>
            {sourcePreviewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={sourcePreviewUrl} alt="Mock official portrait" className="absolute inset-x-[18%] bottom-0 h-[76%] w-[64%] rounded-t-[44%] object-cover object-top mix-blend-multiply grayscale-[15%]" />
            ) : (
              <div className="absolute inset-x-[18%] bottom-0 flex h-[76%] flex-col items-center justify-end">
                <div className="mb-[-6px] h-14 w-14 rounded-full border border-ink/10 bg-[#c9bca9]" />
                <div className="h-24 w-28 rounded-t-[48px] bg-[#2f3a40]" />
              </div>
            )}
            <div className="pointer-events-none absolute inset-x-3 top-[24%] border-t border-measurement/45" />
            <div className="pointer-events-none absolute inset-x-3 top-[38%] border-t border-measurement/25" />
            <div className="pointer-events-none absolute inset-y-3 left-1/2 border-l border-measurement/25" />
          </div>
        </div>

        <div className="flex flex-col justify-between">
          <div>
            <p className="text-sm leading-6 text-slate">
              Mock preview uses a local browser image; production will return expiring URLs compatible with wx.previewImage, wx.downloadFile, and web download flows.
            </p>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">Spec</dt><dd className="mt-1 font-semibold">{template?.label ?? '—'} · {template?.size ?? '—'}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">Background</dt><dd className="mt-1 font-semibold">{selectedBackground}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">fileId</dt><dd className="mt-1 truncate font-mono text-xs">{task?.officialResult?.fileId ?? '—'}</dd></div>
              <div className="rounded-2xl border border-ink/10 bg-paper/60 p-3"><dt className="text-slate">expiresAt</dt><dd className="mt-1 truncate font-mono text-xs">{task?.officialResult?.expiresAt ?? '—'}</dd></div>
            </dl>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <a aria-disabled={!succeeded} href={task?.officialResult?.previewUrl ?? '#'} className={`rounded-2xl px-4 py-3 text-sm font-semibold ${succeeded ? 'bg-ink text-porcelain' : 'pointer-events-none bg-line text-slate'}`}>Preview URL</a>
            <a aria-disabled={!succeeded} href={task?.officialResult?.downloadUrl ?? '#'} className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${succeeded ? 'border-ink/15 text-ink' : 'pointer-events-none border-line text-slate'}`}>Download URL</a>
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-[20px] border border-ink/10 bg-ink p-4 text-porcelain">
        <p className="font-mono text-[10px] uppercase tracking-[0.26em] text-[#b7c9cc]">AI Enhance lane</p>
        <p className="mt-2 text-sm leading-6 text-[#d8d1c4]">
          Optional preview remains disabled in Phase 2. It will never replace this official result card or expose provider keys/base URLs in the client.
        </p>
      </div>
    </section>
  );
}
