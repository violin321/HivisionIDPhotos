import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './features/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--ink)',
        graphite: 'var(--graphite)',
        slate: 'var(--slate)',
        paper: 'var(--paper)',
        porcelain: 'var(--porcelain)',
        line: 'var(--line)',
        measurement: 'var(--measurement)',
        amber: 'var(--amber)',
      },
      boxShadow: {
        panel: '0 28px 80px var(--panel-shadow)',
      },
    },
  },
  plugins: [],
};

export default config;
