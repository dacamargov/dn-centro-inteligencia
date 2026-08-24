/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      // Paleta corporativa de dichter & neira, tomada de las variables globales
      // del sitio: cian #33BDEE, azul #0D5CAB, navy #1C293A sobre fondo blanco.
      //
      // El sitio de D&N es claro y el azul claro es lo que lo identifica, así que
      // el centro de mando va en tema claro: lienzo levemente azulado, tarjetas
      // blancas y el cian reservado para el dato vivo. La rampa `dn` es normal
      // (50 el más claro, 950 el más oscuro), no una escala de superficies.
      colors: {
        dn: {
          50:  '#F1F8FD',
          100: '#DCEEFB',
          200: '#B8DEF6',
          300: '#7FC8EE',
          400: '#33BDEE',  // cian de marca — relleno de gráficas y acentos vivos
          500: '#1785C6',
          600: '#0D5CAB',  // azul corporativo — acción primaria y texto de acento
          700: '#0A4784',
          800: '#1C293A',  // navy de marca — cabecera y superficies oscuras
          900: '#141E2B',
          950: '#0C1420',
        },
        // Superficies y tinta del tema claro.
        lienzo:  '#EDF3F9',  // fondo de la aplicación
        nieve:   '#F6F9FC',  // paneles hundidos dentro de una tarjeta
        marco:   '#D8E3EE',  // bordes y separadores
        tinta:   '#14263B',  // texto principal
        grafito: '#3E556F',  // texto secundario
        humo:    '#6C7F93',  // texto terciario y etiquetas
        acero: {
          300: '#C7CCD1',
          400: '#969CA2',  // gris corporativo
          500: '#7A8189',
          600: '#5B636C',
          700: '#3E4650',
        },
      },
      animation: {
        'pulse-slow': 'pulse 2.5s ease-in-out infinite',
        'flash': 'flash 0.6s ease-out',
        'slide-in-right': 'slide-in-right 0.45s cubic-bezier(0.22, 1, 0.36, 1) both',
        'truck': 'truck-bounce 0.9s ease-in-out infinite',
        'agent-glow': 'agent-glow 2.4s ease-in-out infinite',
        'agent-sparkle': 'agent-sparkle 2.4s ease-in-out infinite',
        'blob-drift-a': 'blob-drift-a 28s ease-in-out infinite',
        'blob-drift-b': 'blob-drift-b 36s ease-in-out infinite',
        'blob-pulse': 'blob-pulse 9s ease-in-out infinite',
        'grid-shift': 'grid-shift 18s linear infinite',
      },
      keyframes: {
        flash: {
          '0%': { backgroundColor: 'rgba(51, 189, 238, 0.18)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'slide-in-right': {
          '0%':   { transform: 'translateX(120%)', opacity: '0' },
          '60%':  { transform: 'translateX(-4px)', opacity: '1' },
          '100%': { transform: 'translateX(0)',    opacity: '1' },
        },
        'truck-bounce': {
          '0%, 100%': { transform: 'translateX(0) translateY(0)' },
          '25%': { transform: 'translateX(2px) translateY(-1px)' },
          '50%': { transform: 'translateX(4px) translateY(0)' },
          '75%': { transform: 'translateX(2px) translateY(-1px)' },
        },
        'agent-glow': {
          '0%, 100%': {
            boxShadow:
              '0 0 0 0 rgba(51, 189, 238, 0.55), 0 0 18px -4px rgba(51, 189, 238, 0.55)',
          },
          '50%': {
            boxShadow:
              '0 0 0 8px rgba(51, 189, 238, 0), 0 0 28px -2px rgba(13, 92, 171, 0.9)',
          },
        },
        'agent-sparkle': {
          '0%, 100%': { transform: 'rotate(0deg) scale(1)',      opacity: '1' },
          '50%':      { transform: 'rotate(14deg) scale(1.12)',  opacity: '0.85' },
        },
        'blob-drift-a': {
          '0%, 100%': { transform: 'translate3d(0,0,0) scale(1)',            opacity: '0.55' },
          '33%':      { transform: 'translate3d(60px, -40px, 0) scale(1.08)', opacity: '0.75' },
          '66%':      { transform: 'translate3d(-30px, 30px, 0) scale(0.95)', opacity: '0.6' },
        },
        'blob-drift-b': {
          '0%, 100%': { transform: 'translate3d(0,0,0) scale(1)',             opacity: '0.45' },
          '40%':      { transform: 'translate3d(-50px, 50px, 0) scale(1.1)',  opacity: '0.7' },
          '75%':      { transform: 'translate3d(40px, -20px, 0) scale(0.92)', opacity: '0.5' },
        },
        'blob-pulse': {
          '0%, 100%': { transform: 'scale(1)',    opacity: '0.35' },
          '50%':      { transform: 'scale(1.18)', opacity: '0.6' },
        },
        'grid-shift': {
          '0%':   { backgroundPosition: '0 0' },
          '100%': { backgroundPosition: '40px 40px' },
        },
      },
    },
  },
  plugins: [],
};
