import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                // Unified premium color palette - Deep violet/indigo theme
                primary: {
                    50: "#f5f3ff",
                    100: "#ede9fe",
                    200: "#ddd6fe",
                    300: "#c4b5fd",
                    400: "#a78bfa",
                    500: "#8b5cf6",
                    600: "#7c3aed",
                    700: "#6d28d9",
                    800: "#5b21b6",
                    900: "#4c1d95",
                    950: "#2e1065",
                },
                accent: {
                    50: "#fdf4ff",
                    100: "#fae8ff",
                    200: "#f5d0fe",
                    300: "#f0abfc",
                    400: "#e879f9",
                    500: "#d946ef",
                    600: "#c026d3",
                    700: "#a21caf",
                    800: "#86198f",
                    900: "#701a75",
                },
                surface: {
                    50: "#fafafa",
                    100: "#f4f4f5",
                    200: "#e4e4e7",
                    300: "#d4d4d8",
                    400: "#a1a1aa",
                    500: "#71717a",
                    600: "#52525b",
                    700: "#3f3f46",
                    800: "#27272a",
                    900: "#18181b",
                    950: "#09090b",
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            },
            boxShadow: {
                'glow': '0 0 20px rgba(139, 92, 246, 0.35)',
                'glow-lg': '0 0 40px rgba(139, 92, 246, 0.4)',
                'glow-accent': '0 0 20px rgba(217, 70, 239, 0.35)',
                'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.1)',
                'card': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
                'card-hover': '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.2)',
            },
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'gradient-primary': 'linear-gradient(135deg, #8b5cf6 0%, #d946ef 100%)',
                'gradient-dark': 'linear-gradient(135deg, #18181b 0%, #27272a 50%, #18181b 100%)',
                'gradient-glass': 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(217, 70, 239, 0.05) 100%)',
            },
            animation: {
                'gradient': 'gradient 8s ease infinite',
                'float': 'float 6s ease-in-out infinite',
                'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
                'slide-up': 'slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                'slide-down': 'slide-down 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                'fade-in': 'fade-in 0.3s ease-out',
                'scale-in': 'scale-in 0.2s ease-out',
                'shimmer': 'shimmer 2s linear infinite',
            },
            keyframes: {
                gradient: {
                    '0%, 100%': { backgroundPosition: '0% 50%' },
                    '50%': { backgroundPosition: '100% 50%' },
                },
                float: {
                    '0%, 100%': { transform: 'translateY(0px)' },
                    '50%': { transform: 'translateY(-10px)' },
                },
                'pulse-glow': {
                    '0%, 100%': { opacity: '1', boxShadow: '0 0 20px rgba(139, 92, 246, 0.4)' },
                    '50%': { opacity: '0.8', boxShadow: '0 0 30px rgba(139, 92, 246, 0.6)' },
                },
                'slide-up': {
                    '0%': { opacity: '0', transform: 'translateY(10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                'slide-down': {
                    '0%': { opacity: '0', transform: 'translateY(-10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                'fade-in': {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                'scale-in': {
                    '0%': { opacity: '0', transform: 'scale(0.95)' },
                    '100%': { opacity: '1', transform: 'scale(1)' },
                },
                shimmer: {
                    '0%': { backgroundPosition: '-200% 0' },
                    '100%': { backgroundPosition: '200% 0' },
                },
            },
            borderRadius: {
                '4xl': '2rem',
            },
        },
    },
    plugins: [],
};

export default config;
