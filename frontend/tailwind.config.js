/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Same palette as the original VectorRAG_Demo.html so the rebuilt
        // UI looks the same to the team while now being backed by a real
        // FastAPI + PostgreSQL/pgvector service instead of client-only JS.
        brand: {
          DEFAULT: "#1f6f52",
          dark: "#12291f",
          light: "#e6f0ea",
        },
        bg: "#f7f6f3",
        ink: "#1c1c1c",
        muted: "#6b6b6b",
        border: "#e3e0d9",
        mark: "#ffe38a",
      },
    },
  },
  plugins: [],
};
