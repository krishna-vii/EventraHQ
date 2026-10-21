import { spawn } from "node:child_process";
import { resolve } from "node:path";
if (!process.env.LOCAL_DB_ADMIN_PASSWORD) {
  console.error("Set LOCAL_DB_ADMIN_PASSWORD in this session before running the disposable local database assertions. See docs/database.md.");
  process.exit(1);
}
const child = spawn("psql", ["-h", "127.0.0.1", "-p", "54322", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-f", resolve(import.meta.dirname, "../supabase/tests/foundation.sql")], {
  env: { ...process.env, PGPASSWORD: process.env.LOCAL_DB_ADMIN_PASSWORD, PGCONNECT_TIMEOUT: "3" }, stdio: "inherit", windowsHide: true,
});
child.on("error", () => { console.error("psql is unavailable. Install the PostgreSQL client in the qualified local environment."); process.exitCode = 1; });
child.on("exit", (code) => { process.exitCode = code ?? 1; });
