/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        surface2: 'var(--surface-2)',
        line: 'var(--border)',
        ink: 'var(--text)',
        ink2: 'var(--text-2)',
        accent: 'var(--accent)',
        allow: 'var(--allow)',
        ask: 'var(--ask)',
        block: 'var(--block)',
        info: 'var(--info)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: '12px',
        chip: '8px',
        pill: '999px',
      },
      boxShadow: {
        'glow-accent': '0 0 0 3px rgba(200,150,62,0.25)',
      },
    },
  },
  plugins: [],
}
