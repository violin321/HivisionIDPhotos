# Frontend v2 Phase 0/1

Branch: `feat/frontend-v2`

This phase introduces the multi-platform frontend foundation without changing the official `IDCreator` processing chain and without removing the existing Gradio UI.

## Added in this phase

- `api/contract.md` documents the miniapp-compatible API contract for config, uploads, tasks, templates, and health.
- `packages/shared/src/` contains lightweight shared types, enums, compliance copy, and Precision Studio design tokens.
- `web/` contains a Next.js + React + TypeScript + Tailwind scaffold for the Web v2 first screen/upload workflow.

## Web scaffold

The Web v2 scaffold is a mock-only Precision Studio shell:

```bash
cd web
npm install
npm run build
```

The page shows:

- upload area
- upload → specification → task → result → AI preview steps
- miniapp-compatible API status cards
- task status model (`queued`, `processing`, `succeeded`, `failed`, `expired`)
- explicit separation between official ID photo results and optional AI enhance previews

## Legacy Gradio retained

The legacy Gradio application remains in place. This phase does not delete Gradio, does not replace the formal ID photo pipeline, and does not route production traffic to the new web scaffold.

## Security note

Frontend and miniapp clients must never receive provider API keys or GPT-image-2 credentials/base URLs. AI enhance calls are server-side only.
