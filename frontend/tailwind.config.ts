import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#1e1e2e',
          light: '#ffffff',
        },
        panel: {
          DEFAULT: '#252540',
          light: '#f0f0f5',
        },
        border: {
          DEFAULT: '#3a3a5c',
          light: '#d0d0e0',
        },
        accent: {
          DEFAULT: '#4f8cff',
          hover: '#3a6fd8',
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
