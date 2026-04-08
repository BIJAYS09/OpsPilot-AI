/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:  ['var(--font-geist-sans)', 'ui-sans-serif'],
        mono:  ['var(--font-geist-mono)', 'ui-monospace'],
        display: ['var(--font-geist-sans)', 'ui-sans-serif'],
      },
      colors: {
        // Base surface
        bg: {
          base:    '#080c12',
          surface: '#0d1520',
          raised:  '#121d2e',
          border:  '#1e2d42',
          muted:   '#1a2638',
        },
        // Brand
        brand: {
          DEFAULT: '#00c2ff',
          dim:     '#0090c0',
          glow:    'rgba(0,194,255,0.15)',
        },
        // Semantics
        ok:      '#10d17a',
        warn:    '#f59e0b',
        danger:  '#ef4444',
        info:    '#3b82f6',
        // Text
        ink: {
          DEFAULT: '#e2eaf6',
          muted:   '#7a96b8',
          faint:   '#3d5470',
        },
      },
      boxShadow: {
        glow:       '0 0 24px rgba(0,194,255,0.12)',
        'glow-ok':  '0 0 18px rgba(16,209,122,0.15)',
        'glow-warn':'0 0 18px rgba(245,158,11,0.18)',
        'glow-err': '0 0 18px rgba(239,68,68,0.18)',
        card:       '0 1px 3px rgba(0,0,0,0.4)',
      },
      borderRadius: {
        panel: '10px',
      },
      animation: {
        'pulse-slow':  'pulse 3s ease-in-out infinite',
        'blink':       'blink 1.2s step-end infinite',
        'slide-in':    'slideIn 0.3s ease-out',
        'fade-in':     'fadeIn 0.4s ease-out',
      },
      keyframes: {
        blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
        slideIn: { from: { transform: 'translateY(8px)', opacity: 0 }, to: { transform: 'translateY(0)', opacity: 1 } },
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
