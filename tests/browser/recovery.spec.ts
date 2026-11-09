import { test, expect } from '@playwright/test';

test('shortlist asks the API for saved IDs before pagination', async ({ page }) => {
  const response = await page.request.get('/api/v1/artists');
  const artist = (await response.json()).items.at(-1);
  await page.addInitScript(id => localStorage.setItem('eventrahq.saved.v1', JSON.stringify([id])), artist.id);
  const query = page.waitForRequest(request => request.url().includes('artist_ids='));
  await page.goto('/saved');
  expect(new URL((await query).url()).searchParams.get('artist_ids')).toBe(artist.id);
  await expect(page.locator('.artist-card')).toHaveCount(1);
  await expect(page.locator('.artist-card')).toContainText(artist.name);
  await page.reload();
  await expect(page.locator('.artist-card')).toContainText(artist.name);
});

test('account failure never saves silently into guest storage', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.fulfill({ status: 503, json: { detail: 'Account connection unavailable.' } }));
  await page.goto('/artists');
  await expect(page.locator('.artist-card').first()).toBeVisible();
  await page.locator('.save-button').first().click();
  await expect(page.locator('main').getByRole('alert')).toContainText('Check your account connection');
  expect(await page.evaluate(() => localStorage.getItem('eventrahq.saved.v1'))).toBeNull();
});
