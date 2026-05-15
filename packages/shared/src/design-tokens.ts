export const precisionStudioTokens = {
  color: {
    ink: '#121417',
    graphite: '#252a2f',
    slate: '#69737d',
    paper: '#f4f0e8',
    porcelain: '#fbfaf7',
    line: '#d8d1c4',
    measurement: '#1f6f78',
    amber: '#c57b28',
    success: '#2f7d5b',
    danger: '#a94438',
  },
  radius: {
    panel: '28px',
    card: '18px',
    control: '12px',
  },
  shadow: {
    panel: '0 28px 80px rgba(18, 20, 23, 0.16)',
    ruler: 'inset 0 0 0 1px rgba(18, 20, 23, 0.08)',
  },
  typography: {
    display: 'var(--font-display)',
    body: 'var(--font-body)',
    mono: 'var(--font-mono)',
  },
} as const;
