'use client';

import { useRef, useState } from 'react';

type UploadBayProps = {
  file: File | null;
  previewUrl: string | null;
  isUploading: boolean;
  onSelect: (file: File) => void;
};

export function UploadBay({ file, previewUrl, isUploading, onSelect }: UploadBayProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function pickFile(candidate?: File) {
    if (candidate && candidate.type.startsWith('image/')) onSelect(candidate);
  }

  return (
    <div
      className={`relative overflow-hidden rounded-[28px] border border-dashed p-5 transition ${
        dragging ? 'border-amber bg-amber/10' : 'border-measurement/45 bg-measurement/5'
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
      <div className="absolute right-5 top-5 hidden rounded-full border border-ink/10 bg-porcelain/70 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-slate md:block">
        wx.uploadFile aligned
      </div>
      <div className="grid gap-5 md:grid-cols-[136px_1fr] md:items-center">
        <div className="relative aspect-[3/4] overflow-hidden rounded-[22px] border border-ink/10 bg-porcelain shadow-inner">
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="Selected portrait preview" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-slate">
              <div className="h-14 w-14 rounded-full border border-ink/10 bg-[#d7cec0]" />
              <span className="max-w-20 text-xs leading-4">Portrait intake</span>
            </div>
          )}
          <div className="pointer-events-none absolute inset-x-4 top-[22%] border-t border-measurement/45" />
          <div className="pointer-events-none absolute inset-x-4 top-[36%] border-t border-measurement/25" />
          <div className="pointer-events-none absolute inset-y-4 left-1/2 border-l border-measurement/25" />
        </div>

        <div>
          <p className="font-mono text-xs uppercase tracking-[0.26em] text-measurement">Upload bay</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">Drop or select a portrait</h2>
          <p className="mt-2 text-sm leading-6 text-slate">
            Browser-only mock. The shape mirrors multipart/form-data upload handles for web, mobile web, and future miniapp clients—no cookie-only assumption.
          </p>
          {file ? (
            <p className="mt-3 font-mono text-xs text-graphite">
              {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB · {file.type || 'image/*'}
            </p>
          ) : null}
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="rounded-2xl bg-ink px-5 py-4 text-sm font-semibold text-porcelain shadow-lg shadow-ink/20 transition hover:-translate-y-0.5 hover:bg-graphite disabled:cursor-wait disabled:opacity-70"
              disabled={isUploading}
            >
              {isUploading ? 'Creating upload handle…' : 'Select portrait'}
            </button>
            <span className="self-center text-xs leading-5 text-slate">JPG / PNG / WebP · handled locally in Phase 2</span>
          </div>
          <input
            ref={inputRef}
            className="sr-only"
            type="file"
            accept="image/*"
            onChange={(event) => pickFile(event.target.files?.[0])}
          />
        </div>
      </div>
    </div>
  );
}
