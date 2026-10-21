import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
});

test('homepage communicates the marketplace and submits working location search', async ({ page }, info) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Extraordinary artists.Unforgettable events.');
  await expect(page.locator('.artist-card')).toHaveCount(4);
  await expect(page.locator('.hero-visual img')).toBeVisible();
  await page.locator('img').evaluateAll(images => images.forEach(img => { (img as HTMLImageElement).loading = 'eager'; }));
  await expect.poll(() => page.locator('img').evaluateAll(images => images.every(img => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBeTruthy();
  await page.screenshot({ path: `test-results/${info.project.name}-homepage.png`, fullPage: true });
  await page.screenshot({ path: `test-results/${info.project.name}-first-screen.png` });
  await page.getByLabel('Event location').selectOption('Mumbai');
  await page.getByLabel('Event type', { exact: true }).selectOption('Wedding');
  await page.getByRole('button', { name: 'Find artists', exact: true }).click();
  await expect(page.locator('.artist-card')).toHaveCount(2);
  await expect(page.locator('.artist-meta').first()).toContainText('Mumbai');
});

test('real local catalogue filters, empty state and recovery', async ({ page }) => {
  await page.goto('/artists');
  await expect(page.locator('.artist-card')).toHaveCount(8);
  await page.getByRole('button', { name: 'DJs', exact: true }).click();
  await expect(page.locator('.artist-card')).toHaveCount(2);
  await page.getByRole('textbox', { name: 'Search artists, sounds or styles' }).fill('a-name-that-does-not-exist');
  await expect(page.locator('.artist-card')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'A different search could be the one.' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear all filters' }).click();
  await expect(page.locator('.artist-card')).toHaveCount(8);
  await page.getByLabel('Sort artists').selectOption('price_low');
  await expect(page.locator('.artist-card h3').first()).toHaveText('Arjun Strings');
});

test('artist dedicated details and saved shortlist persist in this browser', async ({ page }) => {
  await page.goto('/artists');
  const first = page.locator('.artist-card').first();
  await expect(first).toBeVisible();
  const name = await first.locator('h3').innerText();
  await first.getByRole('link', { name: `View ${name}`, exact: true }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(name);
  await expect(page.getByText('No verified reviews yet.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Save artist', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Saved artist', exact: true })).toBeVisible();
  await page.goto('/saved');
  await expect(page.locator('.artist-card')).toHaveCount(1);
  await expect(page.locator('.artist-card h3')).toHaveText(name);
  await page.reload();
  await expect(page.locator('.artist-card')).toHaveCount(1);
});

test('event brief saves and transfers to the assistant', async ({ page }) => {
  await page.goto('/plan');
  await page.getByRole('textbox', { name: 'Event name', exact: true }).fill('Rooftop celebration');
  await page.getByLabel('Starts (your local time)').fill('2027-12-20T18:00');
  await page.getByLabel('Ends (your local time)').fill('2027-12-20T22:00');
  await page.getByRole('spinbutton', { name: 'Artist budget (INR)', exact: true }).fill('50000');
  await page.getByRole('textbox', { name: 'The occasion and the vibe' }).fill('Soulful music for 60 guests');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Draft saved' })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Event name', { exact: true })).toHaveValue('Rooftop celebration');
  await page.getByRole('button', { name: 'Use with AI' }).click();
  await expect(page.locator('#assistant-brief')).toHaveValue(/Rooftop celebration/);
  await expect(page.locator('#assistant-brief')).toHaveValue(/Soulful music for 60 guests/);
});

test('model failure is actionable and never shown as a successful answer', async ({ page }) => {
  await page.route('**/api/v1/assistant/runs', route => route.fulfill({ status: 503, json: { detail: 'Local model is unavailable for this test.' } }));
  await page.goto('/plan');
  await page.locator('#assistant-brief').fill('An acoustic gathering in Pune');
  await page.getByRole('button', { name: 'Find my artists' }).click();
  await expect(page.locator('.ai-error')).toContainText('Local model is unavailable');
  await expect(page.locator('.ai-answer')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Retry recommendation' })).toBeEnabled();
});

test('keyboard filter drawer and narrow viewports stay usable', async ({ page }, info) => {
  for (const width of [320,360,390,768,1024,1440]) {
    await page.setViewportSize({width,height:900});
    await page.goto('/');
    await expect(page.locator('.hero')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `homepage width ${width}`).toBeTruthy();
  }
  await page.setViewportSize({width:390,height:844});
  await page.goto('/artists');
  await expect(page.locator('.artist-card')).toHaveCount(8);
  await page.getByRole('button',{name:'Filters',exact:true}).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`test-results/${info.project.name}-discovery-mobile.png`,fullPage:true});
});

test('unconfigured services never fake account or database readiness', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('status')).toContainText('not configured');
  await page.getByLabel('Email address').fill('test@example.com');
  await page.getByLabel('Password', { exact: true }).fill('not-a-real-password');
  await page.getByRole('button',{name:'Log in',exact:true}).click();
  await expect(page.locator('.notice.error')).toContainText('not configured');
  expect((await page.request.get('/api/v1/health/ready')).status()).toBe(503);
  await page.goto('/account');
  await expect(page.getByRole('status')).toContainText('not configured');
});

test('date filter does not fabricate availability', async ({ page, isMobile }) => {
  await page.goto('/artists');
  await expect(page.locator('.artist-card')).toHaveCount(8);
  if(isMobile) await page.getByRole('button',{name:'Filters',exact:true}).click();
  const root = isMobile ? page.getByRole('dialog') : page.locator('.filter-row');
  await root.getByLabel('Event date',{exact:true}).fill('2027-12-20');
  if(isMobile) await page.getByRole('button',{name:'Show results'}).click();
  await expect(page.locator('.artist-card')).toHaveCount(0);
  await expect(page.getByText('Only artists with a published calendar', {exact:false})).toBeVisible();
});

test('public routes and photography load without broken links or page exceptions', async ({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 for(const path of ['/','/artists','/plan','/saved','/join','/login','/account','/about','/artists/dj-aarya']){
  const response=await page.goto(path);expect(response?.status()).toBe(200);
  await expect(page.getByRole('heading',{level:1})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 }
 expect(errors).toEqual([]);
});
