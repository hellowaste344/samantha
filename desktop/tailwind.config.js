/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        zenon: {
          blue:  "#0e8af0",
          teal:  "#00c9a7",
          pink:  "#f0409e",
          purple:"#7c4dff",
          dark:  "#0a0a0f",
          card:  "#111118",
          border:"#1e1e2e",
          muted: "#8888aa",
        },
      },
      fontFamily: {
        sans: ["Instrument Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "pulse-slow":  "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "spin-slow":   "spin 3s linear infinite",
        "fade-in":     "fadeIn 0.3s ease-in-out",
        "slide-up":    "slideUp 0.3s ease-out",
        "wave":        "wave 1.5s ease-in-out infinite",
        "glow":        "glow 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:  { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { transform: "translateY(12px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
        wave: {
          "0%, 100%": { transform: "scaleY(0.5)" },
          "50%":       { transform: "scaleY(1.5)" },
        },
        glow: {
          "0%, 100%": { boxShadow: "0 0 20px rgba(14,138,240,0.3)" },
          "50%":       { boxShadow: "0 0 40px rgba(14,138,240,0.7)" },
        },
      },
    },
  },
  plugins: [],
};
