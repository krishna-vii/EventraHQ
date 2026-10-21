import { spawn } from "node:child_process";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
const child = spawn(process.execPath, [resolve(root, "node_modules/next/dist/bin/next"), "build", "--webpack"], {
  cwd: resolve(root, "apps/web"), env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" }, stdio: "inherit", windowsHide: true,
});
child.on("error", (error) => { console.error(error.message); process.exitCode = 1; });
child.on("exit", (code) => { process.exitCode = code ?? 1; });
