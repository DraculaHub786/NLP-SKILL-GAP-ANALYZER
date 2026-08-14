/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#4F46E5",
        surface: { light: "#F8F9FA", dark: "#1E1E1E" },
      },
      borderRadius: { xl2: "16px" },
    },
  },
  plugins: [],
};
