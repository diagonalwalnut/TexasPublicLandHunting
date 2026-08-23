import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Frame-Options": "DENY",
  "Cross-Origin-Opener-Policy": "same-origin",
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base:
    process.env.GITHUB_PAGES === "1"
      ? "/TexasPublicLandHunting/"
      : process.env.BASE_PATH || "/",
  server: { headers: SECURITY_HEADERS },
  preview: { headers: SECURITY_HEADERS },
});
