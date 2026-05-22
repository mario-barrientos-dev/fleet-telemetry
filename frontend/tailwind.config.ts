import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ok: "#16a34a",
        warn: "#d97706",
        danger: "#dc2626",
        muted: "#64748b",
      },
    },
  },
  plugins: [],
} satisfies Config;
