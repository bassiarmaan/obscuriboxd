import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Letterboxd-inspired color palette
        lb: {
          dark: '#14181C',
          darker: '#0D1114',
          card: '#1C2228',
          'card-hover': '#242C34',
          border: '#2C3440',
          text: '#99AABB',
          'text-light': '#D8E0E8',
          orange: '#FF8000',
          green: '#00E054',
          blue: '#40BCF4',
          white: '#FFFFFF',
        }
      },
      fontFamily: {
        display: ['Libre Baskerville', 'var(--font-display)', 'serif'],
        body: ['DM Sans', 'var(--font-body)', 'sans-serif'],
        mono: ['DM Mono', 'var(--font-mono)', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out forwards',
        'slide-up': 'slideUp 0.5s ease-out forwards',
        'scale-in': 'scaleIn 0.3s ease-out forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      boxShadow: {
        'glow-green': '0 0 20px rgba(0, 224, 84, 0.2)',
        'glow-orange': '0 0 20px rgba(255, 128, 0, 0.2)',
        'card': '0 4px 12px rgba(0, 0, 0, 0.3)',
      },
    },
  },
  plugins: [],
}
export default config
