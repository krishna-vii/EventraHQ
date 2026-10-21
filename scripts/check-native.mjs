import { readdirSync, existsSync } from "node:fs";
import { resolve, extname } from "node:path";
const root = resolve(import.meta.dirname, "..");
const violations = [];
function inspect(path) {
  for (const entry of readdirSync(path, { withFileTypes: true })) {
    if (["node_modules", ".next", ".venv", ".git", ".pytest_cache", "__pycache__", "test-results", "playwright-report"].includes(entry.name)) continue;
    const full = resolve(path, entry.name);
    if (entry.isDirectory()) {
      if (["android", "ios", "flutter", ".expo"].includes(entry.name)) violations.push(full);
      else inspect(full);
    } else if ([".swift", ".kt", ".dart", ".xcodeproj"].includes(extname(entry.name)) || ["AndroidManifest.xml", "Podfile", "pubspec.yaml"].includes(entry.name)) violations.push(full);
  }
}
inspect(root);
if (violations.length) { console.error("Native application files are prohibited before the Phase 1 acceptance gate:", violations); process.exitCode = 1; }
else console.log("Phase 1 native-code embargo: passed.");
