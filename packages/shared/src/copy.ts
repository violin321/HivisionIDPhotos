export const complianceCopy = {
  consentTitle: 'Photo processing consent',
  consentBody:
    'Your portrait is used only to create the selected ID photo task. Uploads and generated files expire automatically.',
  privacyRetention: 'Default retention: 24 hours for uploads and generated previews.',
  aiDisclaimer:
    'AI enhance is optional, server-side only, and displayed separately from official ID photo output.',
  providerSecretNotice:
    'Provider API keys and GPT-image-2 access are never sent to web or miniapp clients.',
} as const;

export const productCopy = {
  productName: 'HivisionIDPhotos Precision Studio',
  eyebrow: 'Multi-platform ID photo workbench',
  headline: 'A precise, compliant studio for certificate-ready portraits.',
  uploadCta: 'Upload portrait',
  mockNotice: 'Phase 0/1 scaffold uses mock task data and does not call production APIs.',
} as const;
