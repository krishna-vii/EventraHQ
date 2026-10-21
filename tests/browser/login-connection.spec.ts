import { test, expect } from '@playwright/test';

test('connected development login uses the running backend', async ({ page }, info) => {
  test.skip(process.env.EVENTRA_CONNECTED_TESTS !== '1', 'Requires configured development Supabase; enable EVENTRA_CONNECTED_TESTS=1.');
  const response = await page.request.get('/api/v1/session');
  expect(response.status()).toBe(200);
  expect((await response.json()).configured).toBe(true);
  await page.goto('/login');
  await expect(page.getByRole('status')).toContainText('Account service connected');
  await expect(page.getByText(/not configured/)).toHaveCount(0);
  await expect(page.getByLabel('Email address')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `test-results/${info.project.name}-login-connected.png`, fullPage: true });
});

test('temporary session failure is retryable and never called missing configuration', async ({ page }) => {
  let healthy = false;
  await page.route('**/api/v1/session', route => route.fulfill(healthy
    ? { status: 200, json: { user: null, configured: true } }
    : { status: 503, json: { detail: 'Account connection temporarily unavailable.' } }));
  await page.goto('/login');
  await expect(page.locator('main').getByRole('alert')).toContainText('Account connection temporarily unavailable');
  await expect(page.getByText(/not configured/)).toHaveCount(0);
  healthy = true;
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByRole('status')).toContainText('Account service connected');
  await expect(page.locator('main').getByRole('alert')).toHaveCount(0);
});

test('expired session asks for login without claiming Supabase is unconfigured', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.fulfill({ status: 401, json: { detail: 'Refresh your session.' } }));
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({ status: 401, json: { detail: 'Log in again.' } }));
  await page.goto('/account');
  await expect(page.locator('main').getByRole('alert')).toContainText('Your session expired. Log in again.');
  await expect(page.getByText(/not configured/)).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Log in or create an account' })).toHaveAttribute('href', '/login');
});

test('only explicit backend configuration status displays setup required', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.fulfill({ status: 200, json: { user: null, configured: false } }));
  await page.goto('/login');
  await expect(page.getByRole('status')).toContainText('not configured');
  await page.goto('/account');
  await expect(page.getByRole('status')).toContainText('not configured');
});
