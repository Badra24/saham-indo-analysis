/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'brand-dark': '#0A0A0A',
                'brand-card': '#1E1E1E',
                'brand-accent': '#4CAF50',
            },
            fontFamily: {
                mono: ['"Fira Code"', 'monospace'],
            }
        },
    },
    plugins: [],
}
