import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.dirname(fileURLToPath(import.meta.url));

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Frame-Options": "DENY",
  "Cross-Origin-Opener-Policy": "same-origin",
};

const API_PROXY = {
  "/api": {
    target: "http://127.0.0.1:8088",
    changeOrigin: false,
  },
};

function stripAuthDatabase(): Plugin {
  return {
    name: "strip-auth-database",
    closeBundle() {
      const dir = path.join(webRoot, "dist/api/data");
      if (!fs.existsSync(dir)) return;
      for (const name of fs.readdirSync(dir)) {
        if (name === ".htaccess" || name === ".gitignore") continue;
        fs.rmSync(path.join(dir, name), { recursive: true, force: true });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), stripAuthDatabase()],
  base:
    process.env.GITHUB_PAGES === "1"
      ? "/TexasPublicLandHunting/"
      : process.env.BASE_PATH || "/",
  server: { headers: SECURITY_HEADERS, proxy: API_PROXY },
  preview: { headers: SECURITY_HEADERS, proxy: API_PROXY },
});
