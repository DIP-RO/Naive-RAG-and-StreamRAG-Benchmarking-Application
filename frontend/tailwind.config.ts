import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#09121f',
        paper: '#f5f1e8',
        accent: '#f97316',
        accent2: '#14b8a6',
      },
      boxShadow: {
        glow: '0 0 80px rgba(249, 115, 22, 0.18)',
      },
      backgroundImage: {
        'hero-grid':
          'radial-gradient(circle at top left, rgba(249,115,22,0.16), transparent 34%), radial-gradient(circle at top right, rgba(20,184,166,0.14), transparent 26%), linear-gradient(180deg, rgba(9,18,31,1) 0%, rgba(9,18,31,0.96) 100%)',
      },
    },
  },
  plugins: [],
};

export default config;
