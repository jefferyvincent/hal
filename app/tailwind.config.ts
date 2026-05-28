import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        hal: {
          bg: "#050507",
          panel: "#0a0a0d",
          red: "#ff1a1a",
          "red-glow": "#ff3838",
          "red-deep": "#8a0000",
          amber: "#ffb300",
          "amber-bright": "#ffd44a",
          text: "#c8c8d0",
          "text-dim": "#6a6a72",
        },
      },
      fontFamily: {
        mono: ['"Share Tech Mono"', '"Courier New"', "monospace"],
        display: ['"Michroma"', '"Share Tech Mono"', "monospace"],
      },
      keyframes: {
        breathe: {
          "0%,100%": {
            transform: "translate(-50%,-50%) scale(0.95)",
            opacity: "0.35",
          },
          "50%": {
            transform: "translate(-50%,-50%) scale(1.05)",
            opacity: "0.55",
          },
        },
        "listen-pulse": {
          "0%,100%": { transform: "translate(-50%,-50%) scale(1)" },
          "50%": { transform: "translate(-50%,-50%) scale(1.04)" },
        },
        "processing-flicker": {
          "0%,100%": { opacity: "1", transform: "translate(-50%,-50%) scale(1)" },
          "25%": { opacity: "0.7", transform: "translate(-50%,-50%) scale(0.96)" },
          "50%": { opacity: "1", transform: "translate(-50%,-50%) scale(1.02)" },
          "75%": { opacity: "0.8", transform: "translate(-50%,-50%) scale(0.98)" },
        },
        "processing-pupil": {
          "0%,100%": { transform: "translate(-50%,-50%) scale(1)" },
          "50%": { transform: "translate(-50%,-50%) scale(1.4)" },
        },
        "speak-pulse": {
          "0%,100%": {
            transform: "translate(-50%,-50%) scale(1)",
            opacity: "1",
          },
          "50%": {
            transform: "translate(-50%,-50%) scale(1.08)",
            opacity: "0.85",
          },
        },
        "speak-pupil": {
          "0%,100%": { transform: "translate(-50%,-50%) scale(1)" },
          "50%": { transform: "translate(-50%,-50%) scale(1.2)" },
        },
      },
      animation: {
        breathe: "breathe 5s ease-in-out infinite",
        "listen-pulse": "listen-pulse 1.5s ease-in-out infinite",
        "processing-flicker": "processing-flicker 0.4s linear infinite",
        "processing-pupil": "processing-pupil 0.6s ease-in-out infinite",
        "speak-pulse": "speak-pulse 0.5s ease-in-out infinite",
        "speak-pupil": "speak-pupil 0.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
