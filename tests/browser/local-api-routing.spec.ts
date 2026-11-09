import { test, expect } from '@playwright/test';

test('local page server forwards session and validated login requests to the API', async ({ request }) => {
  const direct = 'http://127.0.0.1:3001/api/v1';
  const session = await request.get(`${direct}/session`);
  expect(session.status()).toBe(200);
  expect(session.headers()['content-type']).toContain('application/json');
  expect(await session.json()).toMatchObject({ user: null, configured: expect.any(Boolean) });
  // Invalid input is rejected before contacting Auth; no credentials or account writes.
  const login = await request.post(`${direct}/auth/login`, { data: {}, headers: { origin: 'http://127.0.0.1:3000' } });
  expect(login.status()).toBe(422);
  expect((await login.json()).detail).toEqual(expect.arrayContaining([expect.objectContaining({ loc: ['body', 'email'] })]));
});

test('local forwarding retains origin and session-write checks', async ({ request }) => {
  const direct = 'http://127.0.0.1:3001/api/v1';
  const foreign = await request.post(`${direct}/auth/login`, { data: {}, headers: { origin: 'https://untrusted.example' } });
  expect(foreign.status()).toBe(403);
  const cookieWrite = await request.post(`${direct}/auth/login`, { data: {}, headers: { cookie: 'eventra_access=test-placeholder' } });
  expect(cookieWrite.status()).toBe(403);
  const privateRecords = await request.get(`${direct}/events`);
  expect(privateRecords.status()).toBe(401);
  const unrelated = await request.get('http://127.0.0.1:3001/api/v10/session');
  expect(unrelated.status()).toBe(404);
});
