module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#4F46E5',
        'primary-dark': '#3730A3',
        'primary-light': '#818CF8',
        secondary: '#10B981',
        accent: '#F59E0B',
        danger: '#EF4444',
        'dark-bg': '#0F0F1A',
        'dark-surface': '#1A1A2E',
      },
      fontFamily: {
        sans: ['Sora', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
