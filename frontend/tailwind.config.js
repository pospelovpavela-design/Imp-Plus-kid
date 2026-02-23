/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        // monospace for timestamps, mind-speech, code
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
        // sans-serif for UI labels
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // ── Background layers ──────────────────────────
        void:  '#0a0a0f',   // spec: background
        deep:  '#0d0d14',
        panel: '#111118',
        'panel-raised': '#15151e',

        // ── Borders ────────────────────────────────────
        border:        '#1a1a2a',
        'border-bright':'#252538',
        dim:           '#33334a',

        // ── Text ───────────────────────────────────────
        text:        '#e0e0e0',   // spec: text
        'text-dim':  '#707088',
        'text-bright':'#f0f0f0',

        // ── Primary accent — cold blue (spec: #4a9eff) ──
        accent:      '#4a9eff',
        'accent-dim':'#1a4a8a',
        'accent-glow':'#7ab3ff',  // spec: active node

        // ── Graph colours (spec) ───────────────────────
        'node-base':   '#2a4a7f',  // spec: nodes
        'node-active': '#7ab3ff',  // spec: active node
        'edge-color':  '#1a3a5f',  // spec: edges
        'node-seed':   '#4a2a7f',  // seed concepts (darker purple)

        // ── Semantic ───────────────────────────────────
        gold:      '#d4a017',
        'gold-dim':'#7a5c0a',
        teal:      '#14b8a6',
        red:       '#ff4466',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in':    'fadeIn 0.35s ease-out',
        'slide-up':   'slideUp 0.3s ease-out',
        blink:        'blink 1s step-end infinite',
        scan:         'scan 2s linear infinite',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0', transform: 'translateY(6px)' },  '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideUp: { '0%': { opacity: '0', transform: 'translateY(12px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        blink:   { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
        scan:    { '0%': { backgroundPosition: '0% 0%' }, '100%': { backgroundPosition: '0% 100%' } },
      },
    },
  },
  plugins: [],
}
