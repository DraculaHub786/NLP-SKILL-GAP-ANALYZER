/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#FF7A29",
          hover: "#E8651A",
          subtle: "#FFE8D9",
          dark: "#FF9152",
        },
        surface: {
          canvas: "#F4F4F2",
          card: "#FFFFFF",
          sunken: "#EBEBE8",
          dark: "#17181A",
          darkCard: "#212226",
        },
        ink: {
          primary: "#1C1C1E",
          secondary: "#5F6368",
          muted: "#8A8D91",
          onDark: "#F2F2F0",
        },
        status: {
          critical: "#E0473E",
          major: "#F2994A",
          minor: "#D9A93C",
          info: "#5F9EA0",
          success: "#2FAE6B",
        },
      },
      borderRadius: { xl2: "16px", xl3: "20px" },
      boxShadow: {
        soft: "0 1px 2px rgba(20,20,20,0.04), 0 4px 16px rgba(20,20,20,0.06)",
        liftHover: "0 2px 4px rgba(20,20,20,0.06), 0 8px 24px rgba(20,20,20,0.10)",
      },
    },
  },
  plugins: [],
};
