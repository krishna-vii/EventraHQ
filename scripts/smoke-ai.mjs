import os from "node:os";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
if (!process.argv.includes("--run-live")) throw new Error("This check loads a real local model. Pass --run-live deliberately.");
if (os.freemem() < 4 * 1024 ** 3) throw new Error("Less than 4 GiB free RAM. Defer the live model check until memory is available.");
const origin = "http://127.0.0.1:3000";
const catalogue = await (await fetch(`${origin}/api/v1/artists`)).json();
const allowed = new Set(catalogue.items.map((artist) => artist.id));
const started = performance.now();
const response = await fetch(`${origin}/api/v1/assistant/runs`, {
  method: "POST", headers: { "Content-Type": "application/json", Origin: origin },
  body: JSON.stringify({ brief: "Suggest a fictional DJ for a celebration in Bengaluru. Budget INR 70000. Explain briefly." }),
  signal: AbortSignal.timeout(130_000),
});
const body = await response.text();
if (!response.ok) throw new Error(`Live local assistant returned HTTP ${response.status}: ${body}`);
const resultBlock = body.split("\n\n").find((block) => block.startsWith("event: result"));
if (!resultBlock) throw new Error("The live local assistant did not return a validated result: " + body);
const answer = JSON.parse(resultBlock.split("\n").find((line) => line.startsWith("data: ")).slice(6));
if (!answer.artist_ids.length || !answer.artist_ids.every((id) => allowed.has(id))) throw new Error("Result contained invalid catalogue references.");
const report = { checked_at: new Date().toISOString(), model: "qwen3.5:4b", context: 2048, max_output: 512, elapsed_seconds: Number(((performance.now() - started) / 1000).toFixed(2)), source_mode: catalogue.mode, result: answer, note: "One live functional smoke check, not a capacity or latency qualification." };
const directory = resolve(import.meta.dirname, "../.runtime");
mkdirSync(directory, { recursive: true });
writeFileSync(resolve(directory, "ai-smoke.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
