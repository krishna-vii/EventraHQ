import os from "node:os";
import net from "node:net";
import { spawnSync } from "node:child_process";

const ports = [3000, 3001, 8000, 11434, 54321, 54322, 6379];
const probe = (port) => new Promise((resolve) => {
  const socket = net.createConnection({ port, host: "127.0.0.1", timeout: 500 });
  socket.once("connect", () => { socket.destroy(); resolve({ port, state: "listening" }); });
  socket.once("timeout", () => { socket.destroy(); resolve({ port, state: "not reachable" }); });
  socket.once("error", (error) => resolve({ port, state: error.code === "ECONNREFUSED" ? "not listening" : error.code }));
});
const docker = spawnSync("docker", ["--version"], { encoding: "utf8", windowsHide: true, timeout: 3000 });
console.log(JSON.stringify({
  node: process.version,
  os: `${os.platform()} ${os.release()}`,
  logical_processors: os.availableParallelism(),
  ram_gib: Number((os.totalmem() / 1024 ** 3).toFixed(2)),
  free_ram_gib: Number((os.freemem() / 1024 ** 3).toFixed(2)),
  docker: docker.status === 0 ? docker.stdout.trim() : "unavailable",
  ports: await Promise.all(ports.map(probe)),
  status: "Inventory only. Full database/model capacity qualification is a separate milestone.",
}, null, 2));
