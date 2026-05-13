import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#121417',
        graphite: '#252a2f',
        slate: '#69737d',
        paper: '#f4f0e8',
        porcelain: '#fbfaf7',
        line: '#d8d1c4',
        measurement: '#1f6f78',
        amber: '#c57b28',
      },
      boxShadow: {
        panel: '0 28px 80px rgba(18, 20, 23, 0.16)',
      },
    },
  },
  plugins: [],
};

export default config;
