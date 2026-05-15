'use client';

import { useRef, useState } from 'react';
import { usePreferences } from '../../lib/preferences';

type UploadBayProps = {
  file: File | null;
  previewUrl: string | null;
  isUploading: boolean;
  onSelect: (file: File) => void;
};

export function UploadBay({ file, previewUrl, isUploading, onSelect }: UploadBayProps) {
  const { t } = usePreferences();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function pickFile(candidate?: File) {
    if (candidate && candidate.type.startsWith('image/')) onSelect(candidate);
  }

  return (
    <section
      className={`workflow-step-card relative overflow-hidden rounded-[24px] border p-4 transition sm:rounded-[26px] sm:p-5 ${
        dragging ? 'border-amber bg-amber/10' : 'border-measurement/35 bg-porcelain/76'
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        pickFile(event.dataTransfer.files[0]);
      }}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-measurement">01 · {t('uploadBay')}</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] sm:text-3xl">{t('dropSelectPortrait')}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate">{t('uploadHelp')}</p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="shrink-0 rounded-2xl bg-ink px-5 py-3 text-sm font-semibold text-porcelain shadow-lg shadow-ink/15 transition hover:-translate-y-0.5 hover:bg-graphite disabled:cursor-wait disabled:opacity-70"
          disabled={isUploading}
        >
          {isUploading ? t('creatingUpload') : t('selectPortrait')}
        </button>
      </div>

      <div className="mt-4 flex flex-col gap-3 rounded-[20px] border border-ink/10 bg-paper/55 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-slate">{t('materialSummary')}</p>
          {file ? (
            <p className="mt-1 break-all font-mono text-xs text-graphite">
              {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB · {file.type || 'image/*'} · {previewUrl ? t('materialReady') : t('creatingUpload')}
            </p>
          ) : (
            <p className="mt-1 text-sm text-slate">{t('noMaterial')}</p>
          )}
        </div>
        <span className="shrink-0 text-xs leading-5 text-slate">{t('uploadTypes')}</span>
      </div>
      <input ref={inputRef} className="sr-only" type="file" accept="image/*" onChange={(event) => pickFile(event.target.files?.[0])} />
    </section>
  );
}
