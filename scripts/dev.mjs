import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import net from "node:net";
import { startGateway, ORIGIN } from "./gateway.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
if (existsSync(resolve(root, ".env"))) process.loadEnvFile(resolve(root, ".env"));
const apiRoot = resolve(root, "services/api");
const python = process.env.EVENTRA_PYTHON || resolve(apiRoot, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const next = resolve(root, "node_modules/next/dist/bin/next");
if (!existsSync(python) || !existsSync(next)) {
  console.error("Install the web dependencies and API virtual environment first. See README.md.");
  process.exit(1);
}

async function assertFree(port) {
  await new Promise((resolvePromise, reject) => {
    const probe = net.createServer();
    probe.once("error", () => reject(new Error(`Port ${port} is occupied or unavailable. Stop its known owner before starting EventraHQ.`)));
    probe.listen(port, "127.0.0.1", () => probe.close(resolvePromise));
  });
}
for (const port of [3000, 3001, 8000]) await assertFree(port);

const children = [];
let closing = false;
const gateway = await startGateway();
async function close(code = 0) {
  if (closing) return;
  closing = true;
  gateway.close();
  gateway.closeAllConnections();
  await Promise.allSettled(children.map((child) => new Promise((done) => {
    if (!child.pid || child.exitCode !== null) return done();
    if (process.platform === "win32") {
      // Next.js forks its server: stop only the descendant tree of our owned child.
      const killer = spawn("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
      killer.on("error", done); killer.on("exit", done);
    } else {
      try { process.kill(-child.pid, "SIGTERM"); } catch { /* already stopped */ }
      done();
    }
  })));
  process.exit(code);
}
function launch(label, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, APP_ENV: "local", APP_ORIGIN: ORIGIN, NEXT_TELEMETRY_DISABLED: "1", PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"], windowsHide: true, detached: process.platform !== "win32",
  });
  children.push(child);
  child.stdout.on("data", (data) => process.stdout.write(`[${label}] ${data}`));
  child.stderr.on("data", (data) => process.stderr.write(`[${label}] ${data}`));
  child.on("error", (error) => { console.error(`${label} failed: ${error.message}`); close(1); });
  child.on("exit", (code) => { if (!closing) { console.error(`${label} exited (${code}).`); close(code || 1); } });
}
launch("api", python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--no-access-log"], apiRoot);
launch("web", process.execPath, [next, "dev", "--hostname", "127.0.0.1", "--port", "3001"], resolve(root, "apps/web"));
console.log(`\nEventraHQ workspace: ${ORIGIN}\nLauncher PID: ${process.pid}. Account workflows require configured Supabase. Press Ctrl+C to stop these owned processes.\n`);
process.on("SIGINT", () => close());
process.on("SIGTERM", () => close());
