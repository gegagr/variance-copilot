import type { Config } from "tailwindcss";

// Finance-SaaS direction: light surfaces, a single indigo accent, semantic colors for
// variance direction and card status. Inter + tabular figures. Not a terminal.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#4f46e5", // indigo-600
          fg: "#ffffff",
          subtle: "#eef2ff", // indigo-50
        },
        favorable: "#047857", // emerald-700
        unfavorable: "#b91c1c", // red-700
        surface: "#ffffff",
        canvas: "#f8fafc", // slate-50
        border: "#e2e8f0", // slate-200
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      fontVariantNumeric: {
        tabular: "tabular-nums lining-nums",
      },
    },
  },
  plugins: [],
} satisfies Config;
