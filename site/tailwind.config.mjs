/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ocean: {
          50:  '#f0f9ff',
          100: '#e0f2fe',
          500: '#0891b2',
          600: '#0e7490',
          700: '#155e75',
        },
        cream: '#faf9f7',
        sand:  '#f0ede8',
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        sans:    ['DM Sans', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
