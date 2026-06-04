/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontSize: {
        'kiosk-sm':  ['1.125rem', { lineHeight: '1.5' }],
        'kiosk-base':['1.375rem', { lineHeight: '1.5' }],
        'kiosk-lg':  ['1.75rem',  { lineHeight: '1.3' }],
        'kiosk-xl':  ['2.25rem',  { lineHeight: '1.2' }],
      },
      minHeight: {
        'touch': '48px',
      },
      minWidth: {
        'touch': '48px',
      },
    },
  },
  plugins: [],
}
