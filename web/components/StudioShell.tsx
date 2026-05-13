import { apiCards, mockTask, stages } from '../lib/mock-data';

function StatusPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-measurement/25 bg-measurement/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-measurement">
      {children}
    </span>
  );
}

function PortraitPlate() {
  return (
    <div className="relative mx-auto aspect-[3/4] w-full max-w-[310px] rounded-[30px] border border-ink/15 bg-[#ece6da] p-5 shadow-panel">
      <div className="absolute -left-7 top-10 h-56 w-5 border-y border-ink/25">
        <div className="ruler-edge h-full opacity-70" />
      </div>
      <div className="absolute -right-5 bottom-8 rounded-full border border-amber/40 bg-amber/10 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.22em] text-amber">
        mock
      </div>
      <div className="h-full rounded-[22px] border border-ink/10 bg-porcelain p-4">
        <div className="flex h-full flex-col items-center justify-end overflow-hidden rounded-[18px] bg-gradient-to-b from-[#f8f7f2] via-[#e8e0d1] to-[#d7cec0]">
          <div className="mb-[-10px] h-24 w-24 rounded-full border border-ink/10 bg-[#c9bca9] shadow-inner" />
          <div className="h-40 w-44 rounded-t-[70px] border border-ink/10 bg-[#2f3a40]" />
        </div>
      </div>
    </div>
  );
}

export default function StudioShell() {
  return (
    <main className="min-h-screen px-5 py-6 text-ink md:px-10 lg:px-14">
      <section className="mx-auto max-w-7xl overflow-hidden rounded-[34px] border border-ink/10 bg-porcelain/70 shadow-panel">
        <div className="grid min-h-[calc(100vh-3rem)] lg:grid-cols-[1.05fr_.95fr]">
          <div className="relative p-7 md:p-11 lg:p-14">
            <div className="mb-12 flex items-center justify-between border-b border-ink/10 pb-4">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-slate">HivisionIDPhotos</p>
                <h1 className="mt-2 font-serif text-4xl leading-[0.95] tracking-[-0.04em] md:text-6xl">
                  Precision Studio
                </h1>
              </div>
              <StatusPill>Phase 0/1</StatusPill>
            </div>

            <div className="grid gap-8 lg:grid-cols-[1fr_240px]">
              <div>
                <p className="max-w-2xl text-lg leading-8 text-graphite md:text-xl">
                  A measured, compliance-first workbench for certificate-ready portraits across web and future miniapp clients.
                </p>
                <div className="mt-8 rounded-[28px] border border-dashed border-measurement/45 bg-measurement/5 p-5">
                  <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="font-mono text-xs uppercase tracking-[0.26em] text-measurement">Upload bay</p>
                      <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">Drop or select a portrait</h2>
                      <p className="mt-2 text-sm leading-6 text-slate">
                        Mock-only scaffold. The production contract uses multipart/form-data and returns expiring upload/file handles.
                      </p>
                    </div>
                    <button className="rounded-2xl bg-ink px-5 py-4 text-sm font-semibold text-porcelain shadow-lg shadow-ink/20 transition hover:-translate-y-0.5 hover:bg-graphite">
                      Upload portrait
                    </button>
                  </div>
                </div>
              </div>
              <PortraitPlate />
            </div>

            <div className="mt-10 grid gap-3 md:grid-cols-5">
              {stages.map((stage, index) => (
                <div key={stage.label} className="precision-card rounded-[18px] p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-slate">0{index + 1}</span>
                    <span className={stage.state === 'active' ? 'h-2 w-2 rounded-full bg-amber' : 'h-2 w-2 rounded-full bg-line'} />
                  </div>
                  <h3 className="mt-4 font-semibold">{stage.label}</h3>
                  <p className="mt-2 text-xs leading-5 text-slate">{stage.detail}</p>
                </div>
              ))}
            </div>
          </div>

          <aside className="border-t border-ink/10 bg-[#e8e0d1]/60 p-7 md:p-11 lg:border-l lg:border-t-0 lg:p-12">
            <div className="rounded-[28px] border border-ink/10 bg-porcelain/80 p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-semibold tracking-[-0.03em]">Task model</h2>
                <StatusPill>{mockTask.task.status}</StatusPill>
              </div>
              <dl className="mt-6 space-y-4 text-sm">
                <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-slate">uploadId</dt><dd className="font-mono text-xs">{mockTask.upload.uploadId}</dd></div>
                <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-slate">fileId</dt><dd className="font-mono text-xs">{mockTask.upload.fileId}</dd></div>
                <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-slate">taskId</dt><dd className="font-mono text-xs">{mockTask.task.taskId}</dd></div>
                <div className="flex justify-between gap-4"><dt className="text-slate">states</dt><dd className="font-mono text-xs">queued / processing / succeeded / failed / expired</dd></div>
              </dl>
            </div>

            <div className="mt-5 rounded-[28px] border border-ink/10 bg-ink p-6 text-porcelain">
              <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-[#b7c9cc]">AI boundary</p>
              <h3 className="mt-3 text-xl font-semibold">Enhance previews stay separate.</h3>
              <p className="mt-3 text-sm leading-6 text-[#d8d1c4]">
                Official ID photo output remains distinct from optional server-side AI enhance. No API key or provider base URL is exposed in this client.
              </p>
            </div>

            <div className="mt-5 grid gap-3">
              {apiCards.map(([method, path, purpose]) => (
                <div key={path} className="grid grid-cols-[64px_1fr] gap-3 rounded-2xl border border-ink/10 bg-porcelain/70 p-4 text-sm">
                  <span className="font-mono text-xs font-bold text-measurement">{method}</span>
                  <div>
                    <p className="font-mono text-xs text-ink">{path}</p>
                    <p className="mt-1 text-xs leading-5 text-slate">{purpose}</p>
                  </div>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
