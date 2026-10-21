import http from "node:http";
import { pathToFileURL } from "node:url";

export const ORIGIN = "http://127.0.0.1:3000";
const hopHeaders = new Set(["connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"]);

export function destination(path) {
  if (/^\/api\/v1(?:\/|\?|$)/.test(path)) return 8000;
  if (/^\/(auth|storage|realtime)\/v1(?:\/|\?|$)/.test(path)) return 54321;
  return 3001;
}

function allowed(request) {
  const origin = request.headers.origin;
  return request.headers.host === "127.0.0.1:3000"
    && (!origin || origin === ORIGIN)
    && request.url?.startsWith("/") && !request.url.startsWith("//");
}

function headersFor(request, upgrade = false) {
  const headers = Object.fromEntries(Object.entries(request.headers).filter(([name]) =>
    !hopHeaders.has(name) && !name.startsWith("x-forwarded-") && name !== "forwarded"));
  headers.host = "127.0.0.1:3000";
  headers["x-forwarded-host"] = "127.0.0.1:3000";
  headers["x-forwarded-proto"] = "http";
  headers["x-forwarded-for"] = "127.0.0.1";
  if (upgrade) {
    headers.connection = "Upgrade";
    headers.upgrade = request.headers.upgrade;
  }
  return headers;
}

export function createGateway() {
  const server = http.createServer((request, response) => {
    if (!allowed(request)) {
      response.writeHead(403, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ detail: "Use the local workspace at " + ORIGIN }));
      return;
    }
    const upstream = http.request({
      hostname: "127.0.0.1", port: destination(request.url), path: request.url,
      method: request.method, headers: headersFor(request),
    }, (incoming) => {
      const headers = Object.fromEntries(Object.entries(incoming.headers).filter(([name]) => !hopHeaders.has(name)));
      response.writeHead(incoming.statusCode ?? 502, headers);
      incoming.pipe(response);
      incoming.on("error", () => response.destroy());
    });
    upstream.setTimeout(130_000, () => upstream.destroy(new Error("Upstream timeout")));
    upstream.on("error", () => {
      if (response.headersSent) return response.destroy();
      response.writeHead(502, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      response.end(JSON.stringify({ detail: "A local service is unavailable. Check the workspace terminal and retry." }));
    });
    request.on("aborted", () => upstream.destroy());
    response.on("close", () => { if (!response.writableEnded) upstream.destroy(); });
    request.pipe(upstream);
  });

  server.on("upgrade", (request, socket, head) => {
    if (!allowed(request)) { socket.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n"); return; }
    const upstream = http.request({ hostname: "127.0.0.1", port: destination(request.url), path: request.url, headers: headersFor(request, true) });
    upstream.on("upgrade", (incoming, peer, upstreamHead) => {
      upstream.setTimeout(0);
      peer.setTimeout(0);
      socket.write(`HTTP/1.1 ${incoming.statusCode} ${incoming.statusMessage}\r\n`);
      for (const [key, value] of Object.entries(incoming.headers)) {
        if (Array.isArray(value)) value.forEach((item) => socket.write(`${key}: ${item}\r\n`));
        else if (value !== undefined) socket.write(`${key}: ${value}\r\n`);
      }
      socket.write("\r\n");
      if (head.length) peer.write(head);
      if (upstreamHead.length) socket.write(upstreamHead);
      peer.pipe(socket); socket.pipe(peer);
      peer.on("error", () => socket.destroy());
      socket.on("error", () => peer.destroy());
      socket.on("close", () => peer.destroy());
    });
    upstream.setTimeout(10_000, () => upstream.destroy(new Error("WebSocket handshake timeout")));
    upstream.on("response", (incoming) => { incoming.resume(); socket.end("HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n"); });
    upstream.on("error", () => socket.destroy());
    socket.on("close", () => upstream.destroy());
    upstream.end();
  });
  server.requestTimeout = 140_000;
  server.headersTimeout = 15_000;
  return server;
}

export async function startGateway() {
  const server = createGateway();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(3000, "127.0.0.1", resolve);
  });
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { await startGateway(); console.log(`EventraHQ local gateway: ${ORIGIN}`); }
  catch (error) { console.error(`Gateway could not start: ${error.message}`); process.exitCode = 1; }
}
