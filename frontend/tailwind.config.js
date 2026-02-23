/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        // Monospace — timestamps, mind-speech, code
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
        // UI — Russian-friendly sans-serif
        sans: ['Onest', 'Golos Text', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // ── Spec colour tokens ─────────────────────────────────
        'bg-primary':    '#080810',   // void background
        'bg-secondary':  '#0e0e1a',   // nav, panels
        'bg-card':       '#12121f',   // cards, raised surfaces
        'text-primary':  '#dde0f0',   // main text
        'text-secondary':'#7880a0',   // dim / secondary labels
        'accent-blue':   '#3d7fff',   // primary accent
        'accent-gold':   '#c8a84b',   // milestones
        'accent-green':  '#2d9e6b',   // success / добавлено
        border:          '#1e2035',   // all borders
        'node-default':  '#1e3a6e',   // concept graph nodes
        'node-active':   '#4a7fff',   // selected node
        'node-seed':     '#2d5a9e',   // seed concepts

        // ── Aliases — keep old utility names working ───────────
        void:           '#080810',
        deep:           '#0e0e1a',
        panel:          '#12121f',
        'panel-raised': '#161626',
        'border-bright':'#2a2a42',
        dim:            '#33334a',
        text:           '#dde0f0',
        'text-dim':     '#7880a0',
        'text-bright':  '#f0f2ff',
        accent:         '#3d7fff',
        'accent-dim':   '#1a3a7a',
        'accent-glow':  '#7ab3ff',
        gold:           '#c8a84b',
        'gold-dim':     '#6a5820',
        teal:           '#2d9e6b',
        red:            '#e05565',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in':    'fadeIn 0.35s ease-out',
        'slide-up':   'slideUp 0.3s ease-out',
        blink:        'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0', transform: 'translateY(6px)' },  '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideUp: { '0%': { opacity: '0', transform: 'translateY(12px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        blink:   { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
      },
    },
  },
  plugins: [],
}
