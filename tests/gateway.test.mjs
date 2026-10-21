import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createGateway, destination } from "../scripts/gateway.mjs";

test("gateway routes only the intended service prefixes", () => {
  assert.equal(destination("/api/v1/artists?search=band"), 8000);
  assert.equal(destination("/api/v10/other"), 3001);
  assert.equal(destination("/auth/v1/token"), 54321);
  assert.equal(destination("/auth/callback"), 3001);
  assert.equal(destination("/realtime/v1/websocket?apikey=local"), 54321);
  assert.equal(destination("/storage/v1/object/private/file"), 54321);
  assert.equal(destination("/api/not-ours"), 3001);
});

test("gateway rejects foreign hosts and cross-origin callers", async () => {
  const server = createGateway();
  await new Promise((done) => server.listen(0, "127.0.0.1", done));
  try {
    const port = server.address().port;
    const get = (headers) => new Promise((done, reject) => {
      const request = http.get({ host: "127.0.0.1", port, path: "/api/v1/artists", headers }, (response) => {
        response.resume(); response.on("end", () => done(response.statusCode));
      });
      request.on("error", reject);
    });
    assert.equal(await get({ host: "attacker.example" }), 403);
    assert.equal(await get({ host: "127.0.0.1:3000", origin: "https://attacker.example" }), 403);
  } finally { await new Promise((done) => server.close(done)); }
});
