/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      },
      colors: {
        void: '#05050a',
        deep: '#0a0a14',
        panel: '#0f0f1a',
        border: '#1a1a2e',
        'border-bright': '#2a2a4e',
        dim: '#3a3a5e',
        text: '#c0c0d8',
        'text-dim': '#606080',
        'text-bright': '#e8e8f8',
        accent: '#7c7cff',
        'accent-dim': '#4444aa',
        gold: '#d4a017',
        'gold-dim': '#7a5c0a',
        teal: '#14b8a6',
        'teal-dim': '#0a6b62',
        red: '#ff4466',
        'seed-color': '#9966ff',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-in',
        blink: 'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        blink: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
      },
    },
  },
  plugins: [],
}
