import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: { 950: "#08090a", 900: "#0f1011", 800: "#191a1b" },
        accent: { DEFAULT: "#10b981", hi: "#34d399", dim: "rgba(16,185,129,.12)" },
        danger: { DEFAULT: "#f2555a", tx: "#ff8589" },
        warn: "#f5a524",
        idblue: "#9fc5ff",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ["var(--font-display)", "Inter", "sans-serif"],
      },
      keyframes: {
        floaty: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
      animation: {
        floaty: "floaty 7s ease-in-out infinite",
      },
      borderRadius: { s: "6px", m: "8px", l: "12px" },
    },
  },
  plugins: [],
};
export default config;
