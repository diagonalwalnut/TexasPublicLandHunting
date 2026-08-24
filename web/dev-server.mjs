import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.dirname(fileURLToPath(import.meta.url));
const extra = process.argv.slice(2);

const php = spawn("php", ["-S", "127.0.0.1:8088", path.join(webRoot, "api-dev-router.php")], {
  cwd: webRoot,
  stdio: "inherit",
});

php.on("error", (err) => {
  console.error("PHP is required for local accounts (php-cli + php-sqlite3):", err.message);
  process.exit(1);
});

const vite = spawn("npx", ["vite", ...extra], {
  cwd: webRoot,
  stdio: "inherit",
  shell: true,
});

function stop() {
  php.kill("SIGTERM");
  vite.kill("SIGTERM");
}

process.on("SIGINT", stop);
process.on("SIGTERM", stop);

vite.on("exit", (code) => {
  php.kill("SIGTERM");
  process.exit(code ?? 0);
});
