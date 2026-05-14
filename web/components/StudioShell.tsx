'use client';

import { useEffect, useMemo, useState } from 'react';
import { ResultPanel } from '../features/result/ResultPanel';
import { TaskStatusRail } from '../features/idphoto-workflow/TaskStatusRail';
import { WorkflowControls } from '../features/idphoto-workflow/WorkflowControls';
import { UploadBay } from '../features/upload/UploadBay';
import { apiCards, stages } from '../lib/mock-data';
import {
  createTask,
  createUpload,
  getTask,
  templates,
  type BackgroundColor,
  type ProcessingTask,
  type UploadHandle,
} from '../lib/api-client';

function StatusPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-measurement/25 bg-measurement/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-measurement">
      {children}
    </span>
  );
}

function HeroPlate({ previewUrl, background }: { previewUrl: string | null; background: BackgroundColor }) {
  const backgroundTone = {
    white: 'from-[#f8f7f2] via-[#eeeae1] to-[#d7cec0]',
    blue: 'from-[#dbeaf3] via-[#b7d2e6] to-[#86abc9]',
    red: 'from-[#f0c1bc] via-[#d98278] to-[#b84a42]',
    gray: 'from-[#f2f0ea] via-[#d4d0c7] to-[#aaa59b]',
  }[background];

  return (
    <div className="relative mx-auto aspect-[3/4] w-full max-w-[310px] rounded-[30px] border border-ink/15 bg-[#ece6da] p-5 shadow-panel">
      <div className="absolute -left-7 top-10 h-56 w-5 border-y border-ink/25">
        <div className="ruler-edge h-full opacity-70" />
      </div>
      <div className="absolute -right-5 bottom-8 rounded-full border border-amber/40 bg-amber/10 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.22em] text-amber">
        phase 2.5
      </div>
      <div className="h-full rounded-[22px] border border-ink/10 bg-porcelain p-4">
        <div className={`relative h-full overflow-hidden rounded-[18px] bg-gradient-to-b ${backgroundTone}`}>
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="Workbench portrait preview" className="absolute inset-x-[16%] bottom-0 h-[82%] w-[68%] rounded-t-[42%] object-cover object-top mix-blend-multiply grayscale-[10%]" />
          ) : (
            <div className="absolute inset-x-0 bottom-0 flex flex-col items-center justify-end">
              <div className="mb-[-10px] h-24 w-24 rounded-full border border-ink/10 bg-[#c9bca9] shadow-inner" />
              <div className="h-40 w-44 rounded-t-[70px] border border-ink/10 bg-[#2f3a40]" />
            </div>
          )}
          <div className="pointer-events-none absolute inset-x-6 top-[23%] border-t border-measurement/50" />
          <div className="pointer-events-none absolute inset-x-6 top-[37%] border-t border-measurement/25" />
          <div className="pointer-events-none absolute inset-y-6 left-1/2 border-l border-measurement/25" />
        </div>
      </div>
    </div>
  );
}

export default function StudioShell({ username, onLogout }: { username?: string | null; onLogout?: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadHandle | null>(null);
  const [task, setTask] = useState<ProcessingTask | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState(templates[0].templateId);
  const [selectedBackground, setSelectedBackground] = useState<BackgroundColor>('white');
  const [aiPreview, setAiPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const template = useMemo(() => templates.find((item) => item.templateId === selectedTemplate), [selectedTemplate]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function handleSelect(nextFile: File) {
    setBusy(true);
    setFile(nextFile);
    setTask(null);
    setUpload(null);
    setErrorMessage(null);
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return URL.createObjectURL(nextFile);
    });
    try {
      const nextUpload = await createUpload(nextFile);
      setUpload(nextUpload);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Upload failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateTask() {
    if (!upload) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const nextTask = await createTask({
        uploadId: upload.uploadId,
        templateId: selectedTemplate,
        platform: 'web',
        aiMode: aiPreview ? 'preview' : 'none',
        options: {
          background: selectedBackground,
          renderOfficialIdPhoto: true,
          renderAiEnhancePreview: aiPreview,
        },
      });
      setTask(nextTask);
      setBusy(false);

      let polledTask = nextTask;
      for (let tick = 1; tick <= 12; tick += 1) {
        polledTask = await getTask(polledTask, tick);
        setTask(polledTask);
        if (['succeeded', 'failed', 'expired'].includes(polledTask.status)) break;
        await new Promise((resolve) => setTimeout(resolve, 900));
      }
      if (polledTask.status === 'failed' || polledTask.status === 'expired') {
        setErrorMessage(polledTask.error?.message ?? `Task ${polledTask.status}.`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Task creation failed.');
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-6 text-ink md:px-10 lg:px-14">
      <section className="mx-auto max-w-7xl overflow-hidden rounded-[34px] border border-ink/10 bg-porcelain/70 shadow-panel">
        <div className="grid min-h-[calc(100vh-3rem)] lg:grid-cols-[1.08fr_.92fr]">
          <div className="relative p-7 md:p-11 lg:p-14">
            <div className="mb-12 flex items-center justify-between border-b border-ink/10 pb-4">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-slate">HivisionIDPhotos</p>
                <h1 className="mt-2 font-serif text-4xl leading-[0.95] tracking-[-0.04em] md:text-6xl">
                  Precision Studio
                </h1>
              </div>
              <div className="flex items-center gap-3">
                {username ? <span className="hidden font-mono text-[11px] uppercase tracking-[0.22em] text-slate md:inline">{username}</span> : null}
                {onLogout ? (
                  <button
                    type="button"
                    onClick={() => void onLogout()}
                    className="rounded-full border border-ink/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-graphite transition hover:border-ink/35 hover:text-ink"
                  >
                    Logout
                  </button>
                ) : null}
                <StatusPill>Phase 5C</StatusPill>
              </div>
            </div>

            <div className="grid gap-8 lg:grid-cols-[1fr_240px]">
              <div>
                <p className="max-w-2xl text-lg leading-8 text-graphite md:text-xl">
                  A measured, compliance-first workbench for certificate-ready portraits across web and future miniapp clients.
                </p>
                <div className="mt-8">
                  <UploadBay file={file} previewUrl={previewUrl} isUploading={busy && !task} onSelect={handleSelect} />
                </div>
              </div>
              <HeroPlate previewUrl={previewUrl} background={selectedBackground} />
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

            <div className="mt-6">
              <WorkflowControls
                templates={templates}
                selectedTemplate={selectedTemplate}
                selectedBackground={selectedBackground}
                aiPreview={aiPreview}
                canCreate={Boolean(upload)}
                isWorking={busy || task?.status === 'queued' || task?.status === 'processing'}
                onTemplateChange={setSelectedTemplate}
                onBackgroundChange={setSelectedBackground}
                onAiPreviewChange={setAiPreview}
                onCreateTask={handleCreateTask}
              />
            </div>
          </div>

          <aside className="border-t border-ink/10 bg-[#e8e0d1]/60 p-7 md:p-11 lg:border-l lg:border-t-0 lg:p-12">
            <TaskStatusRail upload={upload} task={task} errorMessage={errorMessage} />

            <div className="mt-5 rounded-2xl border border-ink/10 bg-porcelain/70 p-4 text-xs leading-5 text-slate">
              Privacy note: uploads accept JPG/PNG/WebP only, are size-limited, and expire automatically with generated results.
            </div>

            <div className="mt-5">
              <ResultPanel task={task} template={template} selectedBackground={selectedBackground} sourcePreviewUrl={previewUrl} />
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
